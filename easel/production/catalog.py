"""Channels and reference-derived director versions, using the shared domain DB."""
from __future__ import annotations
import json
from .service import WorkService, encode, fail, new_id, now, row


class CreativeCatalog:
    def __init__(self,service:WorkService): self.service=service; self.store=service.store

    def list(self,kind):
        if kind not in {'channels','directors'}:fail('invalid_input','无效配置类型',400)
        with self.store.connection() as conn:
            values=[dict(r) for r in conn.execute(f'SELECT * FROM {kind} ORDER BY created_at,id')]
            for value in values:
                if kind=='channels':
                    value['settings']=json.loads(value.pop('settings_json'))
                    value['director_ids']=[r[0] for r in conn.execute('SELECT director_id FROM channel_directors WHERE channel_id=?',(value['id'],))]
                    value['profile_name']=row(conn,'profile_refs',value['profile_ref'])['name']
                else:
                    value['versions']=[]
                    for r in conn.execute('SELECT * FROM director_revisions WHERE director_id=? ORDER BY revision DESC',(value['id'],)):
                        version=dict(r);version['style']=json.loads(version.pop('style_json'));version['evidence']=json.loads(version.pop('evidence_json'))
                        value['versions'].append(version)
            return values

    def command(self,kind,action,payload,*,command_id,id=None,expected_revision=None):
        if kind not in {'channels','directors'}:fail('invalid_input','无效配置类型',400)
        def execute(conn):
            existing=row(conn,kind,id) if id else None
            if existing and existing['revision']!=expected_revision:fail('stale_revision','设置已变化，请刷新',409)
            result=self._channel(conn,existing,payload) if kind=='channels' else self._director(conn,existing,action,payload)
            return result
        return self.store.execute_command(command_id,{'catalog':kind,'action':action,'id':id,'revision':expected_revision,'payload':payload},execute)

    def _channel(self,conn,existing,data):
        title=str(data.get('name',existing['name'] if existing else '')).strip()
        if not title or len(title)>200:fail('invalid_input','请输入频道名称')
        settings=data.get('settings',json.loads(existing['settings_json']) if existing else {'schema_version':1})
        self.service._validate_settings(settings)
        if existing:
            id=existing['id'];profile=existing['profile_ref']
            if 'profile_ref' in data and self.service._profile(conn,data['profile_ref'])!=profile:
                fail('invalid_input','频道不能改为另一个主人设')
            conn.execute('UPDATE channels SET name=?,settings_json=?,archived=?,revision=revision+1,updated_at=? WHERE id=?',
                (title,encode(settings),int(bool(data.get('archived',existing['archived']))),now(),id))
        else:
            profile=self.service._profile(conn,data.get('profile_ref'))
            if not profile:fail('invalid_input','创建频道须选择已有六维画像；无频道仍可创作')
            id=new_id();stamp=now()
            conn.execute('INSERT INTO channels(id,profile_ref,name,settings_json,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                         (id,profile,title,encode(settings),stamp,stamp))
        if 'director_ids' in data:
            ids=data['director_ids']
            if not isinstance(ids,list) or len(set(ids))!=len(ids):fail('invalid_input','导演关联无效')
            for director in ids:
                if row(conn,'directors',director)['archived']:fail('invalid_input','不能关联已归档导演')
            current=row(conn,'channels',id)['default_director_revision']
            if current and row(conn,'director_revisions',current)['director_id'] not in ids and 'default_director_revision' not in data:
                fail('invalid_input','解除默认导演关联时须明确清除或更换默认')
            conn.execute('DELETE FROM channel_directors WHERE channel_id=?',(id,))
            conn.executemany('INSERT INTO channel_directors(channel_id,director_id) VALUES (?,?)',[(id,d) for d in ids])
        if 'default_director_revision' in data:
            value=data['default_director_revision'] or None
            if value:self.service._director_version(conn,value)
            conn.execute('UPDATE channels SET default_director_revision=? WHERE id=?',(value,id))
        return {'id':id,'revision':row(conn,'channels',id)['revision']}

    def _director(self,conn,existing,action,data):
        if existing is None:
            name=str(data.get('name','')).strip()
            if not name or len(name)>200:fail('invalid_input','请输入导演名称')
            work=row(conn,'works',data.get('work_id',''))
            if work['revision']!=data.get('work_revision'):fail('stale_revision','参考作品输入已变化',409)
            self.service._ensure_idle(conn,work)
            refs=data.get('reference_input_ids',[])
            if not isinstance(refs,list) or not refs or any(not isinstance(ref,str) or not ref for ref in refs) or len(set(refs))!=len(refs):
                fail('invalid_input','请提供本作品中不重复的视频参考句柄')
            for ref in refs:
                input=row(conn,'work_inputs',ref)
                if input['work_id']!=work['id'] or input['kind']!='video':fail('invalid_input','导演拆解须使用本作品中的视频参考')
            id=new_id();stamp=now()
            conn.execute('INSERT INTO directors(id,name,created_at,updated_at) VALUES (?,?,?,?)',(id,name,stamp,stamp))
            if data.get('services'):self.service._insert_grant(conn,work,'planning',data)
            run=self.service._run(conn,work,'planning',target=id,payload={'director_id':id,'reference_input_ids':refs})
            conn.execute("UPDATE tasks SET kind='analyze_director' WHERE run_id=?",(run,))
            return {'id':id,'revision':1,'work_id':work['id'],'run_id':run}
        id=existing['id']
        if action=='revision':
            style=data.get('style');evidence=data.get('evidence')
            if not isinstance(style,dict) or not style.get('visual_style') or not style.get('storytelling') or not evidence:
                fail('invalid_input','导演版本须保留视听风格、叙事方式和参考依据')
            # User edits may refine a derived style, not silently discard its reference provenance.
            prior=conn.execute('SELECT * FROM director_revisions WHERE director_id=? ORDER BY revision DESC LIMIT 1',(id,)).fetchone()
            if not prior:fail('invalid_input','请先完成参考视频拆解')
            if evidence != json.loads(prior['evidence_json']):
                fail('invalid_input','修改风格不能替换拆解证据；新增参考须重新拆解')
            version=new_id();rev=prior['revision']+1
            conn.execute('INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,created_at) VALUES (?,?,?,?,?,?)',
                         (version,id,rev,encode({'schema_version':1,**style}),encode(evidence),now()))
        elif action=='accept':
            version=row(conn,'director_revisions',data.get('revision_id',''))
            artifact=row(conn,'artifacts',data.get('trial_artifact_id',''))
            if version['director_id']!=id or not version['style_confirmed'] or artifact['quality_state']!='passed' or artifact['output_revision'] is None:
                fail('invalid_input','请先确认风格并审阅该版本的合格试片')
            run=row(conn,'runs',artifact['run_id'])
            plan=conn.execute('SELECT payload_json FROM plan_revisions WHERE work_id=? AND revision=?',(artifact['work_id'],run['plan_revision'])).fetchone()
            if not plan or json.loads(plan[0]).get('director_revision_id')!=version['id']:
                fail('invalid_input','试片并非使用该导演版本制作')
            self.service.artifact_path(artifact['id'])
            conn.execute('UPDATE director_revisions SET trial_artifact_id=?,accepted_at=? WHERE id=?',(artifact['id'],now(),version['id']))
        else:
            if 'name' in data:
                if not str(data['name']).strip():fail('invalid_input','导演名称不能为空')
                conn.execute('UPDATE directors SET name=? WHERE id=?',(data['name'],id))
            if 'archived' in data:conn.execute('UPDATE directors SET archived=? WHERE id=?',(int(bool(data['archived'])),id))
            if data.get('style_confirmed'):
                version=row(conn,'director_revisions',data.get('revision_id',''))
                if version['director_id']!=id:fail('invalid_input','导演版本不匹配')
                conn.execute('UPDATE director_revisions SET style_confirmed=1 WHERE id=?',(version['id'],))
        conn.execute('UPDATE directors SET revision=revision+1,updated_at=? WHERE id=?',(now(),id))
        return {'id':id,'revision':existing['revision']+1}
