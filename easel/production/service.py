"""Transactional user commands for independent video works."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from easel.persona import valid_persona_name
from .errors import ProductionError
from .runtime_readiness import require_current_backend
from .store import Store
from .contracts import PlanDocument, VideoSettings, SubtitleSettings, VoiceIdentity
from pydantic import ValidationError


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def encode(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(encode(value).encode()).hexdigest()


def fail(code: str, message: str, status: int = 422):
    raise ProductionError(code, message, status_code=status)


def row(conn: sqlite3.Connection, table: str, id: str) -> dict:
    # Table identifiers are internal constants, never supplied by a request.
    result = conn.execute(f'SELECT * FROM {table} WHERE id=?', (id,)).fetchone()
    if result is None:
        fail("not_found", "对象不存在", 404)
    return dict(result)


def reference_guard(database: Path, *, path: Path | None = None, profile: str | None = None):
    """Consult references without initializing or upgrading a user's database."""
    if not database.is_file():
        return
    try:
        with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            migrated=any(r[1]=='deleted_at' for r in conn.execute('PRAGMA table_info(works)'))
            if profile:
                live_work='AND w.deleted_at IS NULL' if migrated else ''
                found = conn.execute(f'''SELECT 1 FROM profile_refs p WHERE p.name=? AND
                    (EXISTS(SELECT 1 FROM works w WHERE w.profile_ref=p.id {live_work}) OR
                     EXISTS(SELECT 1 FROM channels c WHERE c.profile_ref=p.id))''', (profile,)).fetchone()
                if found:
                    fail("reference_in_use", "该画像仍被作品或频道引用，请先处理关联", 409)
            if path:
                candidate = path.resolve()
                refs = conn.execute('SELECT storage_ref FROM artifacts'+(' WHERE deleted_at IS NULL' if migrated else '')).fetchall()
                refs += conn.execute("SELECT i.source_ref FROM work_inputs i JOIN works w ON w.id=i.work_id WHERE i.kind!='text'"+(" AND w.deleted_at IS NULL" if migrated else "")).fetchall()
                outputs = database.parent.parent
                for (ref,) in refs:
                    resolved = (outputs / ref).resolve()
                    if candidate == resolved or candidate in resolved.parents:
                        fail("reference_in_use", "该文件仍被作品引用，请从作品入口查看删除影响", 409)
    except sqlite3.DatabaseError:
        fail("internal_error", "制作引用记录不可读取，暂不能安全删除", 409)


def retire_profile_reference(database:Path,name:str,remove):
    """Retire identity with filesystem deletion; same-name recreation gets a new ID."""
    if not database.is_file():
        remove();return
    with sqlite3.connect(database) as conn:
        conn.execute('BEGIN IMMEDIATE')
        profile=conn.execute('SELECT id FROM profile_refs WHERE name=?',(name,)).fetchone()
        if profile:
            migrated=any(r[1]=='deleted_at' for r in conn.execute('PRAGMA table_info(works)'))
            live=' AND deleted_at IS NULL' if migrated else ''
            if conn.execute('SELECT 1 FROM works WHERE profile_ref=?'+live,(profile[0],)).fetchone() or conn.execute('SELECT 1 FROM channels WHERE profile_ref=?',(profile[0],)).fetchone():
                fail('reference_in_use','画像仍被作品或频道引用',409)
            conn.execute('UPDATE profile_refs SET archived=1,name=? WHERE id=?',('archived-'+profile[0],profile[0]))
        remove()


class WorkService:
    def __init__(self, store: Store, *, outputs: Path, profiles: Path):
        self.store, self.outputs, self.profiles = store, outputs.resolve(), profiles.resolve()

    def _profile(self, conn, value: str | None) -> str | None:
        if not value:
            return None
        existing = conn.execute('SELECT * FROM profile_refs WHERE id=? OR name=?', (value, value)).fetchone()
        name = existing['name'] if existing else value
        path = (self.profiles / name).resolve()
        if not valid_persona_name(name) or path.parent != self.profiles or not path.is_dir():
            fail("invalid_input", "请选择存在的六维画像")
        if existing:
            if existing['archived']:
                fail("invalid_input", "该画像已归档")
            return existing['id']
        id = new_id()
        conn.execute('INSERT INTO profile_refs(id,name,created_at) VALUES (?,?,?)', (id, name, now()))
        return id

    def profile_snapshot(self, conn, profile_ref) -> dict:
        if not profile_ref:
            return {}
        name = row(conn, 'profile_refs', profile_ref)['name']
        root = (self.profiles / name).resolve()
        if root.parent != self.profiles or not root.is_dir():
            fail("invalid_input", "原画像不可用，请明确选择创作依据")
        result = {}
        for filename in ('identity.md', 'style.md', 'audience.md', 'platforms.md', 'preferences.md', 'memory.md'):
            path = root / filename
            if path.is_symlink():
                fail("invalid_input", "画像文件不能引用目录外内容")
            if path.is_file():
                result[filename[:-3]] = path.read_text(encoding='utf-8')
        return result

    def _event(self, conn, work_id, kind, payload=None, run_id=None):
        return self.store.append_event(conn, work_id, kind, payload or {}, run_id=run_id)

    def _change(self, conn, work, **updates):
        return self.store.bump_work(conn, work['id'], work['revision'], **updates)

    def command(self, action: str, payload: dict, *, command_id: str,
                work_id: str | None = None, expected_revision: int | None = None, _connection=None) -> dict:
        handlers = {'create': self._create, 'input': self._input, 'plan': self._plan,
                    'confirm': self._confirm, 'cancel': self._cancel, 'grant': self._grant,
                    'resume': self._resume, 'accept': self._accept, 'assignment': self._assignment,
                    'basis':self._update_basis, 'fork': self._fork, 'revise': self._revise, 'confirm_revision': self._confirm_revision}
        if action not in handlers:
            fail('invalid_input', '不支持的作品命令', 400)
        # Prevent stale in-memory source from accepting a new production or
        # task resume after code changed on disk. Cancel and Creator acceptance
        # remain available to avoid trapping an existing Work.
        if action not in {'cancel', 'accept'}:
            require_current_backend()
        if action != 'create' and (not work_id or expected_revision is None):
            fail('invalid_input', '修改作品须提供当前版本', 400)
        def execute(conn):
            work = row(conn, 'works', work_id) if work_id else None
            if work and work.get('deleted_at'):fail('not_found','作品已删除',404)
            result = handlers[action](conn, work, payload)
            target = result.get('work_id', work_id)
            if target:
                self._event(conn, target, 'command_accepted', {'action': action})
                result['cursor'] = conn.execute('SELECT COALESCE(MAX(seq),0) FROM events WHERE work_id=?', (target,)).fetchone()[0]
                result['revision'] = row(conn, 'works', target)['revision']
            return result
        return self.store.execute_command(command_id, {'action': action, 'work_id': work_id,
            'expected_revision': expected_revision, 'payload': payload}, execute,
            work_id=work_id, expected_revision=expected_revision, connection=_connection)

    def _create(self, conn, work, data):
        title = str(data.get('title', '')).strip()
        brief = str(data.get('input_text', '')).strip()
        if not title or len(title)>200 or len(brief)>100000:
            fail('invalid_input', '请输入有效作品名称和创作输入', 400)
        profile = self._profile(conn, data.get('profile_ref'))
        channel_id = data.get('channel_id') or None
        settings = {'schema_version': 1}
        def merge_settings(values):
            from .settings import merge_creation_settings
            settings.update(merge_creation_settings(settings,values))
        if profile:
            merge_settings(json.loads(row(conn, 'profile_refs', profile)['settings_json']))
        if channel_id:
            channel = row(conn, 'channels', channel_id)
            if channel['archived'] or channel['profile_ref'] != profile:
                fail('invalid_input', '频道须属于本次选用画像')
            merge_settings(json.loads(channel['settings_json']))
            if channel['default_director_revision']:
                settings['director_revision'] = channel['default_director_revision']
        own_settings = data.get('settings', {})
        self._validate_settings(own_settings)
        merge_settings(own_settings)
        if settings.get('director_revision'):
            self._director_version(conn, settings['director_revision'], trial=bool(settings.get('director_trial')))
        id, stamp = new_id(), now()
        conn.execute('''INSERT INTO works(id,title,input_text,profile_ref,channel_id,settings_json,source_session_id,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?)''',
                     (id,title,brief,profile,channel_id,encode(settings),data.get('session_id'),stamp,stamp))
        context={'channel_basis':json.loads(channel['creative_basis_json']) if channel_id else {},
                 'channel_revision':channel['revision'] if channel_id else None,
                 'settings_source':{'profile_ref':profile,'channel_id':channel_id,'explicit':own_settings}}
        conn.execute('UPDATE works SET creation_context_json=? WHERE id=?',(encode(context),id))
        self._event(conn,id,'work_created',{'title':title})
        return {'work_id':id}

    @staticmethod
    def _validate_settings(settings):
        allowed = {'schema_version','duration_seconds','aspect_ratio','audio_mode','voice','subtitles','director_revision','director_trial'}
        if not isinstance(settings,dict) or set(settings)-allowed:
            fail('invalid_input','作品设置包含未知字段',400)
        if 'duration_seconds' in settings and (isinstance(settings['duration_seconds'],bool) or not isinstance(settings['duration_seconds'],(int,float)) or not 1<=settings['duration_seconds']<=900):
            fail('invalid_input','视频时长须为1～900秒')
        if settings.get('aspect_ratio','9:16') not in {'9:16','16:9'}:
            fail('invalid_input','画幅须为9:16或16:9')
        try:
            if settings.get('voice') is not None: VoiceIdentity.model_validate(settings['voice'])
            if 'subtitles' in settings: SubtitleSettings.model_validate(settings['subtitles'])
        except ValidationError:
            fail('invalid_input','音色或字幕设置无效')
        if settings.get('audio_mode','silent') not in {'silent','music','voice','mixed'}:
            fail('invalid_input','请选择支持的声音模式')

    @staticmethod
    def _director_version(conn,id,trial=False):
        version=row(conn,'director_revisions',id)
        if row(conn,'directors',version['director_id'])['archived']:
            fail('invalid_input','该导演已归档，请重新选择')
        if not version['accepted_at'] and not (trial and version['style_confirmed']):
            fail('invalid_input','导演需先确认风格；未接受版本仅可明确用于试片')
        return version

    def _input(self, conn, work, data):
        if work['active_run_id']:
            active=row(conn,'runs',work['active_run_id'])
            if active['state'] in {'pending','running','waiting_external','needs_decision','paused'}:
                fail('active_run','请先取消当前运行，再修改创作输入',409)
        usage=data.get('usage','reference')
        if usage not in {'must_use','reference'}:
            fail('invalid_input','请选择必用或参考',400)
        if not isinstance(data.get('original_audio',False),bool):fail('invalid_input','原声设置须为明确开关')
        interval=data.get('interval')
        if interval is not None:
            import math
            if not isinstance(interval,dict) or set(interval)!={'start','end'} or any(isinstance(interval[k],bool) or not isinstance(interval[k],(int,float)) or not math.isfinite(interval[k]) for k in ('start','end')) or not 0<=interval['start']<interval['end']:
                fail('invalid_input','原声区间须为有效起止秒数')
        text=data.get('text')
        kind,source,original='text','', ''
        metadata={'schema_version':1,'original_audio':data.get('original_audio',False),'interval':data.get('interval')}
        if text is not None:
            if not isinstance(text,str) or not text.strip() or len(text)>100000:
                fail('invalid_input','文本输入无效',400)
            checksum=hashlib.sha256(text.encode()).hexdigest()
            source='text:'+checksum
        else:
            session=data.get('session_id')
            if not session or (session != work['source_session_id'] and not conn.execute(
                'SELECT 1 FROM work_conversation_links WHERE work_id=? AND ui_session=?',(work['id'],session)).fetchone()):
                fail('permission_missing','附件不属于本作品的来源会话',403)
            attachment=data.get('attachment') or {}
            relative=Path(attachment.get('path',''))
            scope=hashlib.sha256(session.strip().encode()).hexdigest()[:20]
            if relative.is_absolute() or '..' in relative.parts or len(relative.parts)!=4 or relative.parts[:2] != ('_inbox',scope):
                fail('permission_missing','附件路径越界',403)
            source=relative.as_posix()
            expected=hashlib.sha256((scope+'\0'+source).encode()).hexdigest()[:24]
            if attachment.get('id')!=expected:
                fail('permission_missing','附件标识校验失败',403)
            target=(self.outputs / relative).resolve()
            if self.outputs / '_inbox' / scope not in target.parents or not target.is_file() or any(p.is_symlink() for p in [self.outputs/relative,*list((self.outputs/relative).parents)[:3]]):
                fail('permission_missing','附件不存在或引用越界',403)
            checksum=self._file_hash(target)
            original=target.name
            extension=target.suffix.lower()
            kind='image' if extension in {'.png','.jpg','.jpeg','.webp'} else 'video' if extension in {'.mp4','.mov','.webm','.mkv'} else 'audio' if extension in {'.mp3','.wav','.m4a','.flac'} else 'document'
            metadata['source']={'kind':'user_upload','session_id':session,'rights':data.get('rights',{})}
        id=new_id()
        conn.execute('''INSERT INTO work_inputs(id,work_id,kind,usage,source_ref,digest,original_name,text_content,metadata_json,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)''',(id,work['id'],kind,usage,source,checksum,original,text or '',encode(metadata),now()))
        self._change(conn,work,state='discussing',current_plan_revision=None)
        self._event(conn,work['id'],'input_registered',{'input_id':id,'kind':kind,'usage':usage})
        return {'work_id':work['id'],'input_id':id}

    @staticmethod
    def _file_hash(path):
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
        return h.hexdigest()

    def _run(self,conn,work,kind,plan_revision=None,target=None,payload=None):
        stamp=now();id=new_id();task_id=new_id()
        fingerprint=digest({'work':work['id'],'revision':work['revision'],'kind':kind,'plan':plan_revision,'target':target,'payload':payload})
        conn.execute('''INSERT INTO runs(id,work_id,kind,plan_revision,target_ref,graph_version,input_fingerprint,created_at,updated_at)
                        VALUES (?,?,?,?,?,'production-1',?,?,?)''',(id,work['id'],kind,plan_revision,target,fingerprint,stamp,stamp))
        first='plan' if kind=='planning' else 'supply' if kind=='production' else 'revise'
        conn.execute('''INSERT INTO tasks(id,work_id,run_id,kind,plan_revision,input_fingerprint,payload_json,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?)''',(task_id,work['id'],id,first,plan_revision,fingerprint,encode({'schema_version':1,**(payload or {})}),stamp,stamp))
        self._change(conn,work,active_run_id=id,state='discussing' if kind=='planning' else 'producing')
        self._event(conn,work['id'],'run_created',{'kind':kind},run_id=id)
        return id

    def _ensure_idle(self,conn,work):
        if work['active_run_id'] and row(conn,'runs',work['active_run_id'])['state'] in {'pending','running','waiting_external','needs_decision','paused'}:
            fail('active_run','作品已有有效运行，请先处理当前制作',409)

    def _plan(self,conn,work,data):
        self._ensure_idle(conn,work)
        if data.get('generate',True):
            if data.get('services'):
                self._insert_grant(conn,work,'planning',data)
            run_id=self._run(conn,work,'planning',payload={'request':data.get('request',''),'creation_basis':self._basis(conn,work)})
            return {'work_id':work['id'],'run_id':run_id}
        payload=data.get('plan')
        self.validate_plan(conn,work,payload)
        rev=conn.execute('SELECT COALESCE(MAX(revision),0)+1 FROM plan_revisions WHERE work_id=?',(work['id'],)).fetchone()[0]
        payload=self.freeze_plan(conn,work,payload)
        conn.execute('INSERT INTO plan_revisions(id,work_id,revision,payload_json,plan_hash,created_at) VALUES (?,?,?,?,?,?)',
                     (new_id(),work['id'],rev,encode(payload),digest(payload),now()))
        self._change(conn,work,current_plan_revision=rev,state='awaiting_confirmation')
        self._event(conn,work['id'],'plan_created',{'plan_revision':rev})
        return {'work_id':work['id'],'plan_revision':rev,'plan_hash':digest(payload)}

    def _basis(self,conn,work):
        settings=json.loads(work['settings_json'])
        director={}
        if settings.get('director_revision'):
            director=json.loads(self._director_version(conn,settings['director_revision'],bool(settings.get('director_trial')))['style_json'])
        brief=conn.execute('SELECT * FROM work_briefs WHERE work_id=? ORDER BY revision DESC LIMIT 1',(work['id'],)).fetchone()
        channel=row(conn,'channels',work['channel_id']) if work['channel_id'] else None
        return {'conversation_brief': None if not brief else {'revision':brief['revision'],'hash':brief['body_hash'],'body':json.loads(brief['body_json'])},
                'channel_basis':json.loads(work.get('creation_context_json','{}')).get('channel_basis',json.loads(channel['creative_basis_json']) if channel else {}),
                'profile_ref':work['profile_ref'],'profile':self.profile_snapshot(conn,work['profile_ref']),
                'channel_id':work['channel_id'],'settings':settings,'director':director}

    def freeze_plan(self,conn,work,payload,*,basis=None):
        basis=basis or self._basis(conn,work)
        payload={**payload,'schema_version':1,'profile_snapshot':None,
                 'director_revision_id':basis['settings'].get('director_revision'),
                 'conversation_basis':{k:basis.get(k) for k in ('conversation_brief','channel_basis')}}
        if work['profile_ref']:
            content=encode(basis['profile'])
            payload['profile_snapshot']={'profile_ref':work['profile_ref'],'content':content,
                                         'content_hash':hashlib.sha256(content.encode()).hexdigest()}
        self.validate_plan(conn,work,payload)
        return PlanDocument.model_validate(payload).model_dump(mode='json')

    def validate_plan(self,conn,work,payload):
        try:
            plan=PlanDocument.model_validate(payload)
        except ValidationError:
            fail('invalid_input','完整方案的脚本、场景或声音/时长设置无效')
        inputs={r['id'] for r in conn.execute('SELECT id FROM work_inputs WHERE work_id=?',(work['id'],))}
        used={ref for scene in plan.scenes for ref in scene.required_input_ids}
        if not used<=inputs:
            fail('invalid_input','方案引用了本作品之外的输入')
        must={r['id'] for r in conn.execute("SELECT id FROM work_inputs WHERE work_id=? AND usage='must_use'",(work['id'],))}
        if not must<=used:
            fail('invalid_input','方案遗漏必用素材')

    def _insert_grant(self,conn,work,purpose,data,plan_revision=None):
        services=data.get('services',[])
        if not isinstance(services,list) or any(not isinstance(x,dict) or set(x)!={'provider','model','mode'} or not all(isinstance(v,str) and v for v in x.values()) for x in services):
            fail('invalid_input','授权须明确服务、模型和模式')
        image=data.get('image_limit',work['image_limit']); video=data.get('video_limit',work['video_limit'])
        if any(not isinstance(v,int) or isinstance(v,bool) or v<0 for v in (image,video)):
            fail('invalid_input','生成次数须为非负整数')
        if purpose!='production': image=video=0
        if purpose=='production' and (image<work['image_limit'] or video<work['video_limit']):
            fail('invalid_input','追加额度不能重置或减少累计上限')
        id=new_id()
        conn.execute('''INSERT INTO authorization_grants(id,work_id,purpose,plan_revision,target_ref,services_json,allow_ai,image_limit,video_limit,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)''',(id,work['id'],purpose,plan_revision,data.get('target_ref'),encode(services),
                        int(bool(data.get('allow_ai'))) if purpose=='production' else 0,image,video,now()))
        if purpose=='production':
            conn.execute('UPDATE works SET image_limit=?,video_limit=? WHERE id=?',(image,video,work['id']))
        return id

    def _confirm(self,conn,work,data):
        self._ensure_idle(conn,work)
        revision=data.get('plan_revision')
        if revision!=work['current_plan_revision']:
            fail('stale_revision','方案版本已变化，请查看当前方案',409)
        plan=conn.execute('SELECT * FROM plan_revisions WHERE work_id=? AND revision=?',(work['id'],revision)).fetchone()
        if not plan or plan['plan_hash']!=data.get('plan_hash') or plan['confirmed_at']:
            fail('stale_revision','方案摘要不匹配或已确认',409)
        conn.execute('UPDATE plan_revisions SET confirmed_at=? WHERE id=?',(now(),plan['id']))
        grant=self._insert_grant(conn,work,'production',data,revision)
        run=self._run(conn,work,'production',revision,payload={'grant_id':grant})
        self._event(conn,work['id'],'plan_confirmed',{'plan_revision':revision},run_id=run)
        return {'work_id':work['id'],'run_id':run,'grant_id':grant}

    def _cancel(self,conn,work,data):
        stamp=now()
        if work['active_run_id']:
            conn.execute("UPDATE runs SET state='cancelled',cancel_requested=1,owner_epoch=owner_epoch+1,revision=revision+1,updated_at=? WHERE id=? AND state IN ('pending','running','waiting_external','needs_decision','paused')",(stamp,work['active_run_id']))
            conn.execute("UPDATE tasks SET state='cancelled',revision=revision+1,updated_at=? WHERE run_id=? AND state!='succeeded'",(stamp,work['active_run_id']))
        conn.execute("UPDATE operations SET state='cancelled',updated_at=?,revision=revision+1 WHERE work_id=? AND state='reserved'",(stamp,work['id']))
        conn.execute('UPDATE authorization_grants SET revoked_at=? WHERE work_id=? AND revoked_at IS NULL',(stamp,work['id']))
        self._change(conn,work,state='cancelled')
        self._event(conn,work['id'],'run_cancelled',{},run_id=work['active_run_id'])
        return {'work_id':work['id']}

    def _grant(self,conn,work,data):
        purpose=data.get('purpose','production')
        if purpose not in {'planning','preview','production'}: fail('invalid_input','授权用途无效')
        revision=work['current_plan_revision'] if purpose=='production' else None
        if purpose=='production':
            plan=conn.execute('SELECT confirmed_at FROM plan_revisions WHERE work_id=? AND revision=?',(work['id'],revision)).fetchone()
            if not plan or not plan[0]:fail('permission_missing','生产授权须绑定已确认方案')
        grant=self._insert_grant(conn,work,purpose,data,revision)
        self._change(conn,work)
        self._event(conn,work['id'],'authorization_updated',{'purpose':purpose})
        return {'work_id':work['id'],'grant_id':grant}

    def _resume(self,conn,work,data):
        if not work['active_run_id']:fail('invalid_input','没有可恢复运行')
        run=row(conn,'runs',work['active_run_id'])
        if run['cancel_requested'] or run['state'] not in {'needs_decision','paused','waiting_external','failed'}:
            fail('invalid_input','当前运行不能直接恢复')
        task=row(conn,'tasks',data.get('decision_id',''))
        if task['run_id']!=run['id'] or task['state'] not in {'needs_decision','retryable_failed','waiting_external','failed'}:
            fail('stale_revision','需要解决的决定已变化',409)
        conn.execute("UPDATE tasks SET state='pending',error_json=NULL,revision=revision+1,updated_at=? WHERE id=?",(now(),task['id']))
        conn.execute("UPDATE runs SET state='pending',owner_epoch=owner_epoch+1,lease_expires_at=NULL,revision=revision+1,updated_at=? WHERE id=?",(now(),run['id']))
        self._change(conn,work,state='discussing' if run['kind']=='planning' else 'producing')
        self._event(conn,work['id'],'decision_resolved',{'decision_id':task['id']},run_id=run['id'])
        return {'work_id':work['id'],'run_id':run['id']}

    @staticmethod
    def _manual_review_ready(conn, artifact) -> bool:
        """Technical PASS + explicitly skipped semantic Gate, not semantic PASS."""
        if (artifact['kind'] != 'output' or not artifact['displayable'] or
                artifact['output_revision'] is None or artifact['quality_state'] != 'needs_fix'):
            return False
        checks = conn.execute("""SELECT check_kind,status,findings_json
            FROM quality_checks WHERE artifact_id=? AND artifact_digest=?
            ORDER BY created_at DESC,id DESC""",
            (artifact['id'],artifact['digest'])).fetchall()
        if any(c['check_kind']=='semantic' and c['status'] in {'fail','partial'} for c in checks):
            return False
        latest = {}
        for c in checks:
            latest.setdefault(c['check_kind'],c)
        if latest.get('technical') is None or latest['technical']['status'] != 'pass':
            return False
        semantic = latest.get('semantic')
        return bool(semantic and semantic['status']=='not_tested' and
                    json.loads(semantic['findings_json']).get('mode')=='manual_review_only')

    def _accept(self,conn,work,data):
        artifact=row(conn,'artifacts',data.get('output_id',''))
        if artifact.get('deleted_at') or not artifact['displayable']:fail('not_found','成果已删除或不可接受',404)
        manual_ready=self._manual_review_ready(conn,artifact)
        if (artifact['work_id']!=work['id'] or artifact['output_revision'] is None or
                (artifact['quality_state']!='passed' and not manual_ready)):
            fail('quality_blocked','请选择可审阅的技术合格版本')
        if manual_ready:
            # Explicit human confirmation is mandatory, even though the
            # automatic semantic Gate was disabled by this work's operator.
            if data.get('manual_review_confirmed') is not True:
                fail('manual_review_confirmation_required',
                    '此版本尚未自动审查音视频语义，须人工看完整片并明确确认')
            run=row(conn,'runs',artifact['run_id'])
            if run['state']!='succeeded' or work['state']!='reviewable':
                fail('quality_blocked','人工审核必须等待正式制作任务成功结束')
        path=(self.outputs/artifact['storage_ref']).resolve()
        if self.outputs not in path.parents or not path.is_file() or self._file_hash(path)!=artifact['digest']:
            fail('quality_blocked','成片缺失或内容已变化，须重新检查')
        source='explicit_manual_review' if manual_ready else 'explicit_user'
        conn.execute('INSERT INTO acceptances(id,work_id,output_id,source,created_at) VALUES (?,?,?,?,?)',
                     (new_id(),work['id'],artifact['id'],source,now()))
        self._change(conn,work,accepted_output_id=artifact['id'])
        self._event(conn,work['id'],'output_accepted',
                    {'output_id':artifact['id'],'acceptance_mode':source})
        return {'work_id':work['id'],'output_id':artifact['id']}

    def _assignment(self,conn,work,data):
        channel_id=data.get('channel_id') or None
        if channel_id:
            channel=row(conn,'channels',channel_id)
            if channel['archived'] or channel['profile_ref']!=work['profile_ref']:
                fail('invalid_input','频道与作品画像不一致')
        self._change(conn,work,channel_id=channel_id)
        self._event(conn,work['id'],'assignment_changed',{'channel_id':channel_id})
        return {'work_id':work['id']}

    def _confirm_revision(self,conn,work,data):
        from .revisions import confirm_revision_scope
        return confirm_revision_scope(self,conn,work,data)

    def _revise(self,conn,work,data):
        from .revisions import request_revision
        return request_revision(self,conn,work,data)

    def _update_basis(self,conn,work,data):
        self._ensure_idle(conn,work)
        if conn.execute('SELECT 1 FROM plan_revisions WHERE work_id=? AND confirmed_at IS NOT NULL',(work['id'],)).fetchone():
            fail('revision_required','已确认方案的创作变更须走修订，原方案保持不变',409)
        if set(data)-{'settings','input_text'}:fail('invalid_input','只能调整本片设置与内容')
        settings=json.loads(work['settings_json']);patch=data.get('settings',{})
        self._validate_settings(patch)
        if patch.get('director_revision'):self._director_version(conn,patch['director_revision'],bool(patch.get('director_trial')))
        if 'subtitles' in patch:patch={**patch,'subtitles':{**settings.get('subtitles',{}),**patch['subtitles']}}
        settings.update(patch)
        text=data.get('input_text',work['input_text'])
        if not isinstance(text,str) or len(text)>100000:fail('invalid_input','本期内容无效')
        self._change(conn,work,settings_json=settings,input_text=text,current_plan_revision=None,state='discussing')
        self._event(conn,work['id'],'basis_updated',{'settings':settings})
        return {'work_id':work['id']}

    @staticmethod
    def _fork_settings(work,data):
        inherited=data.get('inherit_settings',[])
        if not isinstance(inherited,list) or set(inherited)-{'director_revision','voice','subtitles','duration_seconds','aspect_ratio','audio_mode'}:
            fail('invalid_input','请选择明确沿用的设置')
        original=json.loads(work['settings_json'])
        result={k:original[k] for k in inherited if k in original}
        if 'director_revision' in result and original.get('director_trial'):result['director_trial']=True
        return result

    def _fork(self,conn,work,data):
        profile=row(conn,'profile_refs',work['profile_ref'])['name'] if work['profile_ref'] else None
        result=self._create(conn,None,{'title':data.get('title',work['title']+' · 新作'),'input_text':data.get('input_text',work['input_text']),
            'profile_ref':profile,'channel_id':work['channel_id'],'session_id':data.get('session_id'),'settings':self._fork_settings(work,data)})
        # Copy the explicitly selected movie as a reference, not permission to
        # cut its third-party assets into a new export. No grant is inherited.
        output_id=data.get('output_id')
        if output_id:
            source=row(conn,'artifacts',output_id)
            if source['work_id']!=work['id'] or source['kind']!='output' or source.get('deleted_at') or not source['displayable']:
                fail('invalid_input','请选择原作品的具体可见视频版本')
            from .artifacts import artifact_file
            import shutil
            source_path=artifact_file(self,source)
            target=self.outputs/'works'/result['work_id']/'references'/(source['digest']+'.mp4')
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source_path,target)
            if self._file_hash(target)!=source['digest']:fail('input_changed','原作品在复制时发生变化')
            metadata={'schema_version':1,'original_audio':False,'interval':None,
                'source':{'kind':'prior_work','work_id':work['id'],'output_id':output_id,
                    'rights':{'status':'UNKNOWN'}},
                'constraint':'仅作为新作参考；重新使用其中素材、原声须核对本次使用权，不继承旧授权。'}
            conn.execute('''INSERT INTO work_inputs(id,work_id,kind,usage,source_ref,digest,original_name,text_content,metadata_json,created_at)
                VALUES (?,?,'video','reference',?,?,?,'',?,?)''',
                (new_id(),result['work_id'],target.relative_to(self.outputs).as_posix(),source['digest'],work['title']+' · 版本'+str(source['output_revision']),encode(metadata),now()))
        self._event(conn,result['work_id'],'forked',{'source_work_id':work['id'],'source_output_id':output_id})
        return result

    def snapshot(self,id):
        with self.store.connection() as conn:
            work=row(conn,'works',id)
            if work.get('deleted_at'):fail('not_found','作品已删除',404)
            work.pop('source_session_id',None)
            work['settings']=json.loads(work.pop('settings_json'))
            work['creation_context']=json.loads(work.pop('creation_context_json'))
            brief=conn.execute('SELECT * FROM work_briefs WHERE work_id=? ORDER BY revision DESC LIMIT 1',(id,)).fetchone()
            work['conversation_brief']=json.loads(brief['body_json']) if brief else None
            work['inputs']=[{k:v for k,v in dict(r).items() if k!='source_ref'} for r in conn.execute('SELECT * FROM work_inputs WHERE work_id=? ORDER BY created_at,id',(id,))]
            plans=conn.execute('SELECT * FROM plan_revisions WHERE work_id=? ORDER BY revision DESC',(id,)).fetchall()
            work['plans']=[{**{k:r[k] for k in ('revision','plan_hash','confirmed_at')},'plan':json.loads(r['payload_json'])} for r in plans]
            work['runs']=[dict(r) for r in conn.execute('SELECT * FROM runs WHERE work_id=? ORDER BY created_at,id',(id,))]
            work['tasks']=[dict(r) for r in conn.execute('SELECT * FROM tasks WHERE work_id=? ORDER BY created_at,id',(id,))]
            work['artifacts']=[{k:v for k,v in dict(r).items() if k not in {'storage_ref','metadata_json'}} for r in conn.execute('SELECT * FROM artifacts WHERE work_id=? AND displayable=1 AND deleted_at IS NULL',(id,))]
            bundles={json.loads(r['metadata_json']).get('output_id'):r['id'] for r in conn.execute("SELECT id,metadata_json FROM artifacts WHERE work_id=? AND kind='export_bundle' AND displayable=1 AND deleted_at IS NULL",(id,))}
            for artifact in work['artifacts']:
                if artifact['kind']=='output':
                    artifact['export_artifact_id']=bundles.get(artifact['id'],artifact['id'])
                    artifact['manual_review_required']=self._manual_review_ready(conn,artifact)
            work['progress']=[{'kind':r['kind'],'run_id':r['run_id'],'detail':json.loads(r['payload_json'])} for r in conn.execute("SELECT kind,run_id,payload_json FROM events WHERE work_id=? AND kind IN ('render_progress','quality_progress') ORDER BY seq DESC LIMIT 1",(id,))]
            work['reviews']=[{**dict(r),'changes':json.loads(r['changes_json']),'change_hash':digest(json.loads(r['changes_json']))} for r in conn.execute('SELECT * FROM reviews WHERE work_id=? ORDER BY created_at DESC',(id,))]
            work['cursor']=conn.execute('SELECT COALESCE(MAX(seq),0) FROM events WHERE work_id=?',(id,)).fetchone()[0]
            used={}; pending={}; reserved={}
            for kind in ('IMAGE','VIDEO'):
                records=conn.execute('SELECT state FROM operations WHERE work_id=? AND kind=?',(id,kind)).fetchall()
                used[kind]=sum(r[0] in {'submitted','succeeded','failed_after_submit'} for r in records)
                pending[kind]=sum(r[0] in {'sending','unknown'} for r in records)
                reserved[kind]=sum(r[0]=='reserved' for r in records)
            work['pending_operations']=[dict(r) for r in conn.execute("SELECT id,kind,state FROM operations WHERE work_id=? AND state IN ('sending','unknown')",(id,))]
            work['quota']={k:{'limit':work[k.lower()+'_limit'],'used':used[k],'unknown':pending[k],'reserved':reserved[k],
                              'available':max(0,work[k.lower()+'_limit']-used[k]-pending[k]-reserved[k])} for k in used}
            return work

    def list_works(self,*,after:str|None=None,limit=30,state=None,profile_ref=None,channel_id=None):
        if not 1<=limit<=100:fail('invalid_input','分页数量须为1～100',400)
        where=['deleted_at IS NULL'];args=[]
        if after:where.append('id>?');args.append(after)
        for name,value in [('state',state),('profile_ref',profile_ref),('channel_id',channel_id)]:
            if value is not None:where.append(name+'=?');args.append(value)
        with self.store.connection() as conn:
            rows=conn.execute('SELECT id,title,state,revision,profile_ref,channel_id,accepted_output_id,updated_at FROM works'+
                              (' WHERE '+' AND '.join(where) if where else '')+' ORDER BY id LIMIT ?',(*args,limit+1)).fetchall()
            items=[dict(r) for r in rows[:limit]]
            return {'items':items,'next_cursor':items[-1]['id'] if len(rows)>limit else None}

    def artifact_path(self,id):
        with self.store.connection() as conn:
            artifact=row(conn,'artifacts',id)
            if row(conn,'works',artifact['work_id']).get('deleted_at'):fail('not_found','作品已删除',404)
        path=(self.outputs/artifact['storage_ref']).resolve()
        allowed=self.outputs/'works'/artifact['work_id']
        if artifact.get('deleted_at') or not artifact['displayable'] or allowed not in path.parents or not path.is_file():
            fail('not_found','成果不可预览',404)
        if self._file_hash(path)!=artifact['digest']:fail('quality_blocked','成果内容已变化')
        return path,artifact['media_type']
