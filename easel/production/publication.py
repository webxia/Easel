"""Durable accepted-output publishing; no media generation or automatic retry."""
from __future__ import annotations

import json
from .service import digest, encode, fail, row
from .store import new_id, utc_now


class Publications:
    def __init__(self, service, adapter):
        self.service, self.store, self.adapter = service, service.store, adapter

    def _source(self, conn, work_id, output_id, acceptance_id=None):
        work, artifact = row(conn, 'works', work_id), row(conn, 'artifacts', output_id)
        if (work.get('deleted_at') or artifact.get('deleted_at') or
                work['accepted_output_id'] != output_id or artifact['work_id'] != work_id or
                artifact['kind'] != 'output' or not artifact['displayable']):
            fail('acceptance_changed', '请从当前已接受的具体成片准备发布', 409)
        acceptance = conn.execute('SELECT id FROM acceptances WHERE work_id=? AND output_id=? ORDER BY created_at DESC,id DESC LIMIT 1', (work_id, output_id)).fetchone()
        if not acceptance or acceptance_id and acceptance[0] != acceptance_id:
            fail('acceptance_changed', '接受记录已变化，请重新准备发布', 409)
        if self.service._has_known_quality_failure(conn, artifact):
            fail('quality_blocked', '此版本存在已知检查失败，不能发布', 409)
        path = (self.service.outputs / artifact['storage_ref']).resolve()
        if self.service.outputs not in path.parents or not path.is_file() or self.service._file_hash(path) != artifact['digest']:
            fail('media_changed', '接受版文件缺失或内容变化，不能发布', 409)
        return work, artifact, acceptance[0], path

    def prepare(self, work_id, output_id):
        with self.store.transaction() as conn:
            work, artifact, acceptance, _ = self._source(conn, work_id, output_id)
            existing = conn.execute('SELECT id FROM publication_drafts WHERE acceptance_id=? AND platform=?', (acceptance, 'bilibili')).fetchone()
            if existing:
                conn.execute("UPDATE publication_drafts SET state='draft',revision=revision+1,updated_at=? WHERE id=? AND state='cancelled'",(utc_now(),existing[0]))
                return self._get(conn, existing[0])
            credits = []
            for r in conn.execute('''WITH RECURSIVE deps(id) AS (
                SELECT ? UNION SELECT e.dependency_id FROM artifact_edges e JOIN deps d ON e.artifact_id=d.id)
                SELECT metadata_json FROM artifacts WHERE id IN (SELECT id FROM deps)''', (output_id,)):
                credit = json.loads(r[0]).get('attribution')
                if credit and credit.get('credit_text'):
                    credits.append(credit['credit_text'] + '\n' + credit.get('source_page', ''))
            content = {'title':work['title'], 'body':'', 'tags':[], 'tid':36,
                       'copyright':1, 'source':'', 'action':'submit',
                       'credits':'\n\n'.join(dict.fromkeys(credits)), 'account':None}
            identity, stamp = new_id('pub'), utc_now()
            conn.execute('INSERT INTO publication_drafts(id,work_id,output_id,acceptance_id,media_digest,output_revision,platform,content_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                         (identity, work_id, output_id, acceptance, artifact['digest'], artifact['output_revision'], 'bilibili', encode(content), stamp, stamp))
            self.store.append_event(conn,work_id,'publication_changed',{'draft_id':identity})
            return self._get(conn, identity)

    def _get(self, conn, identity):
        draft = row(conn, 'publication_drafts', identity)
        draft['content'] = json.loads(draft.pop('content_json'))
        draft['last_error'] = json.loads(draft.pop('last_error_json'))
        draft['attempts'] = []
        for r in conn.execute('SELECT * FROM publication_attempts WHERE draft_id=? ORDER BY submitted_at', (identity,)):
            attempt = dict(r)
            for key in ('account','content','receipt','snapshot'):
                attempt[key] = json.loads(attempt.pop(key+'_json'))
            # Sending includes a process lost after reservation: never offer retry.
            attempt['can_reconcile'] = attempt['state'] in {'sending','unknown','verified'}
            draft['attempts'].append(attempt)
        draft['confirmation_hash'] = digest({k:draft[k] for k in ('id','revision','work_id','output_id','acceptance_id','media_digest','content')})
        return draft

    def get(self, identity):
        with self.store.connection() as conn:
            return self._get(conn, identity)

    def list(self, work_id=None):
        with self.store.connection() as conn:
            query = 'SELECT id FROM publication_drafts' + (' WHERE work_id=?' if work_id else '') + ' ORDER BY updated_at DESC'
            return [self._get(conn,r[0]) for r in conn.execute(query,(work_id,) if work_id else ())]

    def save(self, identity, revision, content):
        with self.store.transaction() as conn:
            draft = self._get(conn, identity)
            if draft['revision'] != revision or draft['state'] != 'draft':
                fail('stale_publication', '草稿已变化或已提交，请刷新原记录', 409)
            self._source(conn, draft['work_id'], draft['output_id'], draft['acceptance_id'])
            expected = set(draft['content'])
            if set(content) != expected or content['credits'] != draft['content']['credits'] or content['action'] != 'submit':
                fail('invalid_publication', '发布字段不正确，素材署名和投稿动作不能隐式改变')
            self.adapter.validate(content)
            conn.execute("UPDATE publication_drafts SET content_json=?,last_error_json='{}',revision=revision+1,updated_at=? WHERE id=?", (encode(content),utc_now(),identity))
            return self._get(conn, identity)

    def cancel(self, identity, revision):
        with self.store.transaction() as conn:
            draft=self._get(conn,identity)
            if draft['revision'] != revision or draft['state'] != 'draft':
                fail('stale_publication','已提交的记录不能取消或重发',409)
            conn.execute("UPDATE publication_drafts SET state='cancelled',revision=revision+1,updated_at=? WHERE id=?",(utc_now(),identity))
            return self._get(conn,identity)

    def submit(self, identity, revision, confirmation_hash):
        from .errors import ProductionError
        try:
            return self._submit(identity,revision,confirmation_hash)
        except ProductionError as error:
            with self.store.transaction() as conn:
                conn.execute("UPDATE publication_drafts SET last_error_json=?,updated_at=? WHERE id=? AND state='draft' AND revision=?",
                    (encode({'code':error.code,'message':error.user_message,'submitted':False}),utc_now(),identity,revision))
            raise

    def _submit(self, identity, revision, confirmation_hash):
        with self.store.connection() as conn:
            previous=conn.execute('SELECT confirmation_hash FROM publication_attempts WHERE draft_id=? AND draft_revision=?',(identity,revision)).fetchone()
            if previous:
                if previous[0]!=confirmation_hash:fail('confirmation_changed','确认不匹配',409)
                return self._get(conn,identity)
        # Lock includes both legacy and managed B站 upload. No DB lock across network.
        with self.adapter.session() as session:
            with self.store.connection() as conn:
                draft=self._get(conn,identity)
                old=conn.execute('SELECT id,confirmation_hash FROM publication_attempts WHERE draft_id=? AND draft_revision=?',(identity,revision)).fetchone()
                if old:
                    if old['confirmation_hash'] != confirmation_hash:fail('confirmation_changed','确认不匹配',409)
                    return draft
            self.adapter.validate(draft['content'], final=True)
            account=session.account()
            if account != draft['content']['account']:
                fail('account_changed','实际登录账号已变化，请重新读取账号并确认',409)
            snapshot=session.snapshot()  # failure here is definitely before submit
            with self.store.connection() as conn:
                _,_,_,source_path=self._source(conn,draft['work_id'],draft['output_id'],draft['acceptance_id'])
            staged_path=session.stage_video(source_path,draft['media_digest'])
            with self.store.transaction() as conn:
                draft=self._get(conn,identity)
                if draft['state'] != 'draft' or revision != draft['revision'] or confirmation_hash != draft['confirmation_hash']:
                    fail('confirmation_changed','草稿已变化，请查看最终内容后重新确认',409)
                _,artifact,_,path=self._source(conn,draft['work_id'],draft['output_id'],draft['acceptance_id'])
                if artifact['digest'] != draft['media_digest']:fail('media_changed','成片摘要变化',409)
                pending=conn.execute("""SELECT 1 FROM publication_attempts a
                    JOIN publication_drafts d ON d.id=a.draft_id
                    WHERE d.output_id=? AND a.state IN ('sending','unknown')
                    AND json_extract(a.account_json,'$.uid')=?""",
                    (draft['output_id'],account['uid'])).fetchone()
                if pending:
                    fail('publication_pending','同一成片在此账号有待核实投稿，请先查看原发布记录；重新接受不会解除该状态',409)
                attempt_id,stamp=new_id('publish'),utc_now()
                conn.execute('INSERT INTO publication_attempts(id,draft_id,draft_revision,confirmation_hash,account_json,content_json,state,snapshot_json,submitted_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (attempt_id,identity,revision,confirmation_hash,encode(account),encode(draft['content']),'sending',encode(snapshot),stamp,stamp))
                conn.execute("UPDATE publication_drafts SET state='submitted',last_error_json='{}',updated_at=? WHERE id=?",(stamp,identity))
                self.store.append_event(conn,draft['work_id'],'publication_changed',{'draft_id':identity})
            try:
                # Even rc!=0/timeout may follow a successful remote submission.
                session.upload(staged_path,draft['content'])
                receipt=session.readback(draft['content'],snapshot,stamp)
            except FileNotFoundError:
                # Adapter checks executable availability before upload; unexpected
                # missing files after reservation remain unknown, never auto retry.
                receipt={'outcome':'readback_error','reason':'执行中断；请核实原投稿记录'}
            except Exception:
                receipt={'outcome':'readback_error','reason':'投稿或读回中断；请核实原投稿记录'}
            self._record(attempt_id,receipt)
        return self.get(identity)

    def _record(self, attempt_id, receipt):
        with self.store.transaction() as conn:
            attempt=row(conn,'publication_attempts',attempt_id)
            verified=(receipt.get('outcome')=='verified' and receipt.get('matched') and
                      receipt.get('account')==json.loads(attempt['account_json']))
            # Temporary readback failure cannot erase an already verified post.
            if attempt['state']=='verified' and not verified:return
            conn.execute('UPDATE publication_attempts SET state=?,receipt_json=?,updated_at=? WHERE id=?',
                         ('verified' if verified else 'unknown',encode(receipt),utc_now(),attempt_id))
            draft=row(conn,'publication_drafts',attempt['draft_id'])
            self.store.append_event(conn,draft['work_id'],'publication_changed',{'draft_id':draft['id']})

    def reconcile(self, identity):
        with self.adapter.session() as session:
            draft=self.get(identity)
            if not draft['attempts']:fail('no_attempt','没有已提交记录可核实',409)
            attempt=draft['attempts'][-1]
            if session.account()!=attempt['account']:fail('account_changed','请登录原投稿账号后核实',409)
            try:receipt=session.readback(attempt['content'],attempt['snapshot'],attempt['submitted_at'],known_id=(attempt['receipt'].get('matched') or {}).get('platform_content_id'))
            except Exception:receipt={'outcome':'readback_error','reason':'读回暂不可用，保留原投稿记录'}
            self._record(attempt['id'],receipt)
        return self.get(identity)

    def calendar_items(self):
        return calendar_projection(self.store.path)


def calendar_projection(database):
    """Read-only derived view, including when the production DB is not initialized."""
    from .store import Store
    if not database.is_file():return []
    with Store(database).connection() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='publication_attempts'").fetchone():return []
        items=[]
        for row in conn.execute("SELECT a.*,d.id AS publication_id FROM publication_attempts a JOIN publication_drafts d ON d.id=a.draft_id WHERE a.state='verified'"):
            receipt=json.loads(row['receipt_json']);matched=receipt.get('matched') or {}
            if matched.get('status') not in {'published','已发布','开放浏览'}:continue
            stamp=row['submitted_at'];content=json.loads(row['content_json'])
            items.append({'id':row['id'],'title':content['title'],
                'date':stamp[:10],'time':stamp[11:16],'platform':'B站','status':'published',
                'kind':'content','source':'accepted-publication',
                'note':'具体接受版投稿记录；平台状态：'+matched['status'],
                'publication_id':row['publication_id']})
        return items
