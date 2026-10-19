"""Deliver outcomes of conversation-authorized runs to the same native assistant.

Watches live in existing proposal receipts; result turns reuse the durable native
lifecycle. No UI-generated answers, new production controller or model retries.
"""
from __future__ import annotations

import hashlib
import json

from .production.service import digest, encode, now, row


def watched_receipt(conn, result):
    receipt = dict(result)
    if result.get('work_id') and result.get('run_id'):
        seq = conn.execute('SELECT COALESCE(MAX(seq),0) FROM events WHERE work_id=?', (result['work_id'],)).fetchone()[0]
        receipt['_result_delivery'] = {'seen_seq': seq}
    return receipt


def public_receipt(receipt):
    return {k: v for k, v in receipt.items() if k != '_result_delivery'}


class ConversationResults:
    def __init__(self, bridge):
        self.bridge = bridge
        self.service = bridge.service

    def reserve_next(self):
        """Atomically claim one new outcome; active user turns have priority."""
        with self.service.store.transaction() as conn:
            for record in conn.execute("SELECT t.*,s.ui_session,s.revoked_at FROM conversation_turns t JOIN conversation_segments s ON s.id=t.segment_id WHERE json_extract(t.payload_json,'$.origin')='task_result' AND t.state='reserved' AND s.revoked_at IS NULL ORDER BY t.created_at,t.id").fetchall():
                segment = self.bridge.conversations.segment(conn, record['ui_session'])
                payload = json.loads(record['payload_json'])
                if segment['id'] != record['segment_id'] or segment['work_id'] != payload['work_id'] or row(conn,'works',payload['work_id'])['active_run_id'] != payload['result_event']['run_id']:
                    self.bridge._save(conn,record['id'],payload,'ended')
                    continue
                return self._dispatch(conn,record['id'], record['ui_session'], payload)
            proposals = conn.execute("SELECT p.*,s.ui_session FROM conversation_proposals p JOIN conversation_segments s ON s.id=p.segment_id WHERE p.state='applied' AND s.revoked_at IS NULL AND json_type(p.receipt_json,'$._result_delivery')='object' ORDER BY p.created_at,p.id").fetchall()
            for proposal in proposals:
                receipt = json.loads(proposal['receipt_json'])
                segment = self.bridge.conversations.segment(conn, proposal['ui_session'])
                if segment['id'] != proposal['segment_id'] or segment['work_id'] != receipt['work_id']:
                    continue
                work = row(conn, 'works', receipt['work_id'])
                if work.get('deleted_at') or work['active_run_id'] != receipt['run_id']:
                    continue
                run = row(conn, 'runs', receipt['run_id'])
                if run['state'] not in {'succeeded','needs_decision','failed','paused','cancelled'}:
                    continue
                event = conn.execute("SELECT * FROM events WHERE work_id=? AND run_id=? AND kind IN ('run_completed','decision_required','task_needs_decision','task_failed','run_cancelled') ORDER BY seq DESC LIMIT 1", (work['id'],run['id'])).fetchone()
                if not event or event['seq'] <= receipt['_result_delivery']['seen_seq']:
                    continue
                # A result must never race a user reply or an unresolved native run.
                if conn.execute("SELECT 1 FROM conversation_turns t JOIN conversation_segments s ON s.id=t.segment_id WHERE s.ui_session=? AND t.state IN ('reserved','dispatching','active','unknown')", (segment['ui_session'],)).fetchone():
                    continue
                turn_id = 'result_' + digest([segment['id'],run['id'],event['seq']])[:48]
                receipt['_result_delivery']['seen_seq'] = event['seq']
                conn.execute('UPDATE conversation_proposals SET receipt_json=? WHERE id=?', (encode(receipt),proposal['id']))
                if conn.execute('SELECT 1 FROM conversation_turns WHERE id=?',(turn_id,)).fetchone():
                    continue
                from .conversation_pipeline import pending
                context = pending(self.bridge.conversations, conn, segment)
                snapshot = context['work']
                outputs = [{**a, 'playback_url':f"/api/production/artifacts/{a['id']}/content"} for a in snapshot['artifacts'] if a['kind']=='output' and a['run_id']==run['id']]
                result_event = {'work_id':work['id'],'run_id':run['id'],'seq':event['seq'],'run_state':run['state'],
                                'plan_ready':any(p['revision']==snapshot['current_plan_revision'] and not p['confirmed_at'] for p in snapshot['plans']),
                                'model_result_query_available':False,
                                'tasks':[t for t in snapshot['tasks'] if t['run_id']==run['id']], 'outputs':outputs,
                                'unknown_operations':[dict(r) for r in conn.execute("SELECT id,kind,state FROM operations WHERE work_id=? AND run_id=? AND state='unknown'",(work['id'],run['id']))]}
                prompt = ('【宿主任务结果事件，不是用户新指令或授权】\n'+encode(result_event)+
                    '\n请接续当前创作对话。先读取真实结果；方案成功时展示摘要、完整逐字脚本和分镜，必须先用easel_pipeline offer action=confirm创建本版待确认提案（含素材、配音及剪辑/检查实际需要的模型服务），然后展示返回的范围并提出制作确认问题；剪辑制作或局部修订完成时交付实际视频并说明检查结论，等待反馈。失败时解释具体失败、已完成部分、可行下一步，继续向用户提问。UNKNOWN不得声称自动核实或重新派发，明确当前接口能否查询。不得把本事件当作用户同意，不得自行恢复、改稿、授权或制作。视频用返回的playback_url嵌入<video controls src="...">，不得臆造地址。\n【服务端当前上下文】\n'+encode(context))
                payload = {'origin':'task_result','message':None,'attachments':[], 'result_event':result_event,
                    'work_id':work['id'],'revision':work['revision'], 'session_key':'agent:easel-video:'+segment['id'],
                    'native_session_id':segment['native_session_id'],'run_id':None,'tickets':{},'results':{},'calls':{},'answer':'',
                    'visible_proposals':[p['id'] for p in context['pending']], 'prompt_hash':hashlib.sha256(prompt.encode()).hexdigest(), 'result_prompt':prompt}
                conn.execute('INSERT INTO conversation_turns VALUES (?,?,?,?,?,?)',(turn_id,segment['id'],digest(result_event),encode(payload),'reserved',now()))
                return self._dispatch(conn,turn_id,segment['ui_session'],payload)
        return None

    @staticmethod
    def _dispatch(conn,turn_id,session,payload):
        conn.execute("UPDATE conversation_turns SET state='dispatching' WHERE id=?",(turn_id,))
        return {'turn_id':turn_id,'ui_session':session,'prompt':payload['result_prompt'],'payload':payload}
