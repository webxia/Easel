"""Deliver outcomes of conversation-authorized runs to the same native assistant.

Watches live in existing proposal receipts; result turns reuse the durable native
lifecycle. Known failures use a durable server status reply without a model call.
"""
from __future__ import annotations

import hashlib
import json
import time

from .production.service import digest, encode, now, row


_STAGE_NAMES = {'plan':'方案整理','supply':'素材准备','edit':'剪辑','render':'渲染','quality':'成片检查','revise':'局部修订'}

def failure_details(tasks, state, *, unknown=False):
    labels = {'needs_decision':'制作已暂停', 'failed':'制作失败',
              'paused':'制作已暂停', 'cancelled':'制作已取消'}
    # Repeated exports/checks share a run. Only the newest task for each
    # stage describes its current status; cancelled attempts retain audit data.
    latest={task['kind']:task for task in tasks}
    completed = [_STAGE_NAMES.get(t['kind'], t['kind']) for t in latest.values()
                 if t['state']=='succeeded' and t['kind']!='quality']
    checks=[]
    quality=latest.get('quality')
    if quality:
        result=json.loads(quality.get('result_json') or '{}')
        labels_by_check={
            'technical':{'pass':'技术检查通过','fail':'技术检查未通过'},
            'visual':{'pass':'画面抽样检查通过（仅抽样）','fail':'画面抽样检查发现问题'},
            'semantic':{'pass':'内容检查返回通过结论','fail':'内容检查发现问题',
                        'partial':'内容检查未完整完成','not_tested':'完整语义与声音检查未验证'}}
        checks=[labels_by_check[k][result[k]] for k in labels_by_check if result.get(k) in labels_by_check[k]]
        if not checks:
            checks=['成片检查步骤已结束，结果待核实' if quality['state']=='succeeded' else '成片检查尚未完成']
    issues=[]
    for task in latest.values():
        if task['state'] not in {'needs_decision','failed','retryable_failed'}:continue
        error = json.loads(task.get('error_json') or '{}')
        message = error.get('user_message')
        if message:
            if 'caption exceeds the frame' in message:
                message = '画面文字超出边界，需修正文字位置或字号后才能继续导出'
            if task['kind']=='revise' and message=='工具请求无效、越界或没有新证据':
                message='画面查看请求未能执行，局部修订尚未完成'
            issues.append({'stage':_STAGE_NAMES.get(task['kind'], task['kind']), 'message':message})
    from .conversation_pipeline import has_edit_resume
    next_step=None
    if (not unknown and state in {'needs_decision','failed','paused'} and any(
            t['state'] in {'needs_decision','failed','retryable_failed'} and has_edit_resume(t)
            for t in latest.values())):
        next_step='下一步：你可以在本对话回复「继续制作」。我会核对恢复条件，从原断点继续，保留已有素材和配音。'
    return {'title':labels.get(state, '制作状态待核实'), 'completed_steps':completed,
            'issues':issues, 'check_results':checks, 'next_step':next_step, 'retained_message':'已有方案、素材、配音和执行成果均已保留。',
            'unknown_message':'有调用结果尚待核实，不能自动重发；当前模型接口不能查询该调用结果。' if unknown else None}


def failure_text(tasks, state, *, unknown=False):
    details=failure_details(tasks,state,unknown=unknown)
    lines=[details['title']+'。']
    if details['completed_steps']:lines.append('已完成：'+'、'.join(details['completed_steps'])+'。')
    if details['check_results']:lines.append('检查结果：'+'；'.join(details['check_results'])+'。')
    lines.extend(issue['stage']+'：'+issue['message'] for issue in details['issues'])
    lines.append(details['retained_message'])
    if details['unknown_message']:lines.append(details['unknown_message'])
    if details['next_step']:lines.append(details['next_step'])
    return '\n\n'.join(lines)


def output_text(event):
    """Deliver the current render receipt, not a historical version or model guess."""
    if event.get('outcome') != 'completed' or event.get('unknown_operations'):
        return None
    renders = [t for t in event.get('tasks', []) if t['kind'] == 'render' and t['state'] == 'succeeded']
    if not renders:
        return None
    output_id = json.loads(renders[-1].get('result_json') or '{}').get('output_id')
    output = next((a for a in event.get('outputs', []) if a['id'] == output_id), None)
    if not output:
        return None
    checks = output.get('checks', [])
    labels = []
    technical = [q for q in checks if q['kind'] == 'technical']
    labels.append('技术检查通过' if technical and technical[-1]['status'] == 'pass' else '技术检查结果请查看成片记录')
    visual = [q['findings']['visual_status'] for q in checks if q.get('findings', {}).get('scope') == 'sampled_visual_only' and q['findings'].get('visual_status')]
    if visual:
        labels.append('画面抽样检查通过（仅抽样）' if visual[-1] == 'pass' else '画面抽样检查发现问题')
    semantic = [q for q in checks if q['kind'] == 'semantic' and q.get('findings', {}).get('scope') != 'sampled_visual_only']
    labels.append({'pass':'内容检查返回通过结论','fail':'内容检查发现问题','partial':'内容检查未完整完成'}.get(semantic[-1]['status'] if semantic else None, '完整语义与声音检查未验证'))
    revision = output.get('output_revision')
    title = f'第 {revision} 版已完成，可播放审阅。' if revision else '成片已完成，可播放审阅。'
    return '\n\n'.join([title, f'<video controls src="{output["playback_url"]}"></video>',
                        '检查结果：' + '；'.join(labels) + '。',
                        output.get('delivery', {}).get('message') or '请完整播放后告诉我审阅意见。'])


def production_status(conn, work_id):
    if not work_id:
        return None
    work = conn.execute('SELECT active_run_id,deleted_at FROM works WHERE id=?',(work_id,)).fetchone()
    if not work or work['deleted_at'] or not work['active_run_id']:
        return None
    run = conn.execute('SELECT state FROM runs WHERE id=?',(work['active_run_id'],)).fetchone()
    if not run or run['state'] not in {'needs_decision','failed','paused','cancelled'}:
        return None
    tasks = [dict(t) for t in conn.execute('SELECT kind,state,error_json,result_json FROM tasks WHERE run_id=? ORDER BY created_at,id',(work['active_run_id'],))]
    unknown = conn.execute("SELECT 1 FROM operations WHERE run_id=? AND state='unknown'",(work['active_run_id'],)).fetchone()
    return {'state':run['state'], 'message':failure_text(tasks, run['state'], unknown=bool(unknown)),
            **failure_details(tasks,run['state'],unknown=bool(unknown))}


def result_messages(conn, segment):
    """Restore real result turns at their chronological place in the chat."""
    turns=[dict(t) for t in conn.execute("""SELECT t.* FROM conversation_turns t
        JOIN conversation_segments s ON s.id=t.segment_id WHERE s.ui_session=?
        ORDER BY t.created_at,t.id""",(segment['ui_session'],))]
    decoded=[json.loads(t['payload_json']) for t in turns]
    human=[i for i,p in enumerate(decoded) if p.get('origin','user')=='user' and p.get('message')]
    replies=[]
    for i,(turn,payload) in enumerate(zip(turns,decoded)):
        if turn['segment_id']!=segment['id']:continue
        publication_reply=False
        publication_source=None
        if payload.get('origin')!='task_result':
            # Durable local receipt remains visible even if the model reply is
            # interrupted. Reuse chronological message merging, not a bottom card.
            drafts={r['publication']['id']:r['publication'] for r in payload.get('results',{}).values()
                    if isinstance(r,dict) and r.get('draft_url') and isinstance(r.get('publication'),dict) and r['publication'].get('id')}
            if turn['state']!='ended':continue
            accepted=[]
            if not drafts:
                for p in conn.execute("SELECT body_json,receipt_json FROM conversation_proposals WHERE segment_id=? AND state='applied' AND kind='pipeline'",(segment['id'],)):
                    body=json.loads(p['body_json'])
                    if body['values'].get('action')!='accept' or turn['id'] not in body['source_refs']:continue
                    receipt=json.loads(p['receipt_json'])
                    artifact=conn.execute('SELECT output_revision FROM artifacts WHERE id=? AND work_id=?',(receipt.get('output_id'),segment['work_id'])).fetchone()
                    if artifact:
                        accepted.append('第 '+str(artifact['output_revision'])+' 版已接受并保存到内容库。可准备发布、继续修改或下载成片。')
                        publication_source={'work_id':segment['work_id'],'output_id':receipt['output_id']}
            if not drafts and not accepted:continue
            answer='\n\n'.join('发布草稿已保存，成片版本 '+str(d['output_revision'])+
                '。尚未投稿，请在发布页核对账号和最终内容。\n[查看发布草稿](/#publication='+d['id']+')' for d in drafts.values()) if drafts else '\n\n'.join(accepted)
            error=None;publication_reply=True
        else:
            answer=payload.get('answer','');error=payload.get('delivery_error')
        event=payload.get('result_event',{})
        if turn['state']=='ended' and event.get('outcome')=='blocked':
            answer=failure_text(event['tasks'],event['run_state'],unknown=bool(event.get('unknown_operations')))
            error=None  # Known task failure remains available even if its old explanation was interrupted.
        reply={'role':'assistant','content':answer,'serverTurnId':turn['id']+(':publication' if publication_reply else ''),
               'resultState':turn['state'],'deliveryError':error}
        if publication_source:reply['publicationSource']=publication_source
        following=next((n for n in human if n>i),None)
        if following is not None:
            message=decoded[following]['message']
            reply.update(beforeUserTurnId=turns[following]['id'],beforeUserMessage=message,
                         beforeUserOccurrence=sum(decoded[n]['message']==message for n in human if n<=following))
        replies.append(reply)
    return replies


def watched_receipt(conn, result):
    receipt = dict(result)
    if result.get('work_id') and result.get('run_id'):
        seq = conn.execute('SELECT COALESCE(MAX(seq),0) FROM events WHERE work_id=?', (result['work_id'],)).fetchone()[0]
        receipt['_result_delivery'] = {'seen_seq': seq}
    return receipt


def public_receipt(receipt):
    return {k: v for k, v in receipt.items() if k != '_result_delivery'}


def dialogue_task(task):
    """Keep Worker checkpoints private; only frozen plans are deliverable plans."""
    result = dict(task)
    payload = json.loads(result.get('payload_json') or '{}')
    checkpoint = payload.pop('native_draft_checkpoint', None)
    if checkpoint:
        result['retained_draft'] = True
        result['draft_review'] = checkpoint.get('review')
        result['draft_status'] = '内部草稿，非已冻结方案；不能作为制作确认依据'
    result['payload_json'] = encode(payload)
    return result


def material_search_summary(searches):
    """Project existing evidence only; unknown and unexamined are not failures."""
    groups={}
    network={'network_timeout','network_connection','http_unavailable','http_rate_limited','source_unavailable','invalid_response'}
    for search in searches:
        key=(search.get('scene_id'),search.get('role','visual'),search.get('cue_id'))
        group=groups.setdefault(key,{'scene_id':key[0],'role':key[1],'cue_id':key[2],
            'candidate_count':0,'failures':[],'sources':[],'findings':[]})
        group['candidate_count']+=search.get('candidate_count',0)
        for source in search.get('sources',[]):
            if source not in group['sources']:group['sources'].append(source)
        for failure in search.get('failures',[]):
            if failure not in group['failures']:group['failures'].append(failure)
            code=failure.get('code')
            finding=('search_incomplete' if code in network else 'no_results' if code=='no_results'
                     else 'download_failed' if code=='download_failed' else 'eligibility_unresolved')
            if finding not in group['findings']:group['findings'].append(finding)
    return list(groups.values())


class ConversationResults:
    def __init__(self, bridge):
        self.bridge = bridge
        self.service = bridge.service

    def activity(self,turn_id):
        """Observe only executions actually bound to this native turn."""
        with self.service.store.connection() as conn:
            record=conn.execute('SELECT payload_json FROM conversation_turns WHERE id=?',(turn_id,)).fetchone()
            if not record:return None
            receipts=json.loads(record[0]).get('results',{}).values()
            for receipt in receipts:
                if not receipt.get('run_id'):continue
                run=conn.execute('SELECT state FROM runs WHERE id=? AND work_id=?',(receipt['run_id'],receipt.get('work_id'))).fetchone()
                if not run:continue
                if run['state'] in {'succeeded','needs_decision','failed','paused','cancelled','superseded'}:
                    return '执行已停止，正在整理结果' if run['state']!='succeeded' else '执行已完成，正在整理结果'
                task=conn.execute("SELECT kind FROM tasks WHERE run_id=? AND state!='succeeded' ORDER BY created_at,id LIMIT 1",(receipt['run_id'],)).fetchone()
                labels={'plan':'正在整理完整方案','supply':'正在选择素材','voice':'正在制作配音',
                        'edit':'正在剪辑','render':'正在渲染','quality':'正在检查成片','revise':'正在修订'}
                return labels.get(task['kind'],'正在执行已确认步骤') if task else '正在等待执行结果'
        return None

    @staticmethod
    def event_result(conn, snapshot, run, event):
        searches=[json.loads(r[0]) for r in conn.execute(
            "SELECT payload_json FROM events WHERE work_id=? AND run_id=? AND kind='material_search_completed' ORDER BY seq",
            (snapshot['id'],run['id']))]
        groups=material_search_summary(searches)
        return {'work_id':snapshot['id'],'run_id':run['id'],'seq':event['seq'],'run_state':run['state'],
                'outcome':'completed' if run['state']=='succeeded' else 'blocked',
                'current_plan':next((p for p in snapshot['plans'] if p['revision']==snapshot['current_plan_revision']),None),
                'material_summary':{'searches':groups,
                    'known_gaps':[g for g in groups if not g['candidate_count']],
                    'coverage':'只代表已记录的检索。首个阻断之后的音乐、音效、补料或制作可能尚未执行；不得推断通过或失败。网络失败不等于无素材，候选不等于已下载且适合成片。',
                    'retained_candidates':[dict(a) for a in conn.execute(
                        "SELECT kind,quality_state FROM artifacts WHERE work_id=? AND run_id=? AND kind IN ('image','video','audio') AND deleted_at IS NULL",
                        (snapshot['id'],run['id']))],
                    'candidate_is_approved':False,
                    'note':'仅汇总当前运行已有记录，未追加检索。候选尚不代表通过内容、权益及成片审查；保留方案、素材和回执。'},
                'plan_ready':any(p['revision']==snapshot['current_plan_revision'] and not p['confirmed_at'] for p in snapshot['plans']),
                'model_result_query_available':False,
                'tasks':[dialogue_task(t) for t in snapshot['tasks'] if t['run_id']==run['id']],
                'outputs':[{**a,'playback_url':f"/api/production/artifacts/{a['id']}/content"} for a in snapshot['artifacts'] if a['kind']=='output' and a['run_id']==run['id'] and a['displayable'] and not a.get('deleted_at')],
                'unknown_operations':[dict(r) for r in conn.execute("SELECT id,kind,state FROM operations WHERE work_id=? AND run_id=? AND state='unknown'",(snapshot['id'],run['id']))]}

    def poll(self, request):
        """Read only the committed receipt bound to this native call; never submit.

        Each transaction ends before the plugin sleeps. Run completion, including
        Worker-created QC/repair dependencies, is the existing scope boundary.
        """
        from .production.service import fail
        from .conversation_pipeline import pending
        with self.service.store.transaction() as conn:
            record,payload,segment=self.bridge._current(conn,request)
            identity=request.model_dump(exclude={'ticket','interrupted'})
            if payload['tickets'].get(request.ticket)!=digest(identity):
                fail('ticket_mismatch','工具回执身份不匹配',403)
            fingerprint=digest([request.tool,self.bridge._args(request)])
            receipt=payload['results'].get(fingerprint)
            if receipt is None:fail('receipt_missing','执行回执尚未确认，不会自动重发',409)
            if not (receipt.get('work_id') and receipt.get('run_id')):
                return {'waiting':False,'result':receipt}
            if receipt['work_id']!=segment['work_id']:
                fail('binding_mismatch','回执不属于当前作品',403)
            run=row(conn,'runs',receipt['run_id']);work=row(conn,'works',receipt['work_id'])
            if run['work_id']!=work['id']:fail('binding_mismatch','运行不属于当前作品',403)
            key=run['id']
            waits=payload.setdefault('execution_waits',{})
            wait=waits.setdefault(key,{'work_id':work['id'],'run_id':key})
            if request.interrupted or payload.get('delivery_state')=='interrupted' or work['active_run_id']!=key or work.get('deleted_at'):
                wait['interrupted']=True
                self.bridge._save(conn,record['id'],payload,record['state'])
                return {'waiting':False,'result':{**receipt,'wait_interrupted':True,'production_state':run['state'],
                    'message':'本次同步等待已结束，后台原任务继续；完成后由已有结果订阅回传本对话。现在仅说明正在制作，不要求用户重复确认，不声称失败或完成，不重发或自行恢复UNKNOWN。'}}
            terminal=run['state'] in {'succeeded','needs_decision','failed','paused','cancelled','superseded'}
            event=conn.execute("SELECT * FROM events WHERE work_id=? AND run_id=? AND kind IN ('run_completed','decision_required','task_needs_decision','task_failed','run_cancelled','run_superseded') ORDER BY seq DESC LIMIT 1",(work['id'],key)).fetchone() if terminal else None
            if not event:
                task=conn.execute("SELECT kind,state FROM tasks WHERE run_id=? AND state!='succeeded' ORDER BY created_at,id LIMIT 1",(key,)).fetchone()
                progress_seq=conn.execute('SELECT COALESCE(MAX(seq),0) FROM events WHERE work_id=? AND run_id=?',(work['id'],key)).fetchone()[0]
                return {'waiting':True,'run_state':run['state'],'task':dict(task) if task else None,'progress_seq':progress_seq}
            context=pending(self.bridge.conversations,conn,segment)
            result=self.event_result(conn,context['work'],run,event)
            wait.update(seq=event['seq'],interrupted=False)
            # Worker changes revision while the tool waits; subsequent proposal
            # creation must bind to the actual completed work revision.
            payload['revision']=work['revision']
            self.bridge._save(conn,record['id'],payload,record['state'])
            return {'waiting':False,'result':{**receipt,'execution_result':result,'context':context,
                'delivery_instruction':('本次运行未成功，必须先说明阻断；current_plan为空时不能声称方案成功、不能交付内部草稿冒充方案或提出制作确认。' if result['outcome']=='blocked' else '')+'这是本次已确认执行的真实结果，不是新的用户授权。规划成功：以current_plan交付完整方案、逐字稿和分镜，offer confirm后等待用户确认，不自动制作。参考分析：展示真实分析与待确认风格。制作或修订：嵌入outputs中实际playback_url的视频，按checks分别说明技术、抽帧视觉、完整语义和声音检查；manual_review_required表示待人工审阅，不单凭needs_fix推断存在缺陷；按输出delivery.message说明后续动作，不能替用户接受或投稿。失败或UNKNOWN：结合material_summary一次说明所有已知缺口、已完成步骤、保留成果、合法选项及新增调用费用风险；候选不等于审查通过，不将未执行步骤说成失败。不重发、不许诺远端自动核实。内部编号仅用于工具参数，不要求用户复制编号。'}}

    @staticmethod
    def acknowledge(conn, payload):
        # Receipt consumption happens only with a persisted, non-empty assistant
        # delivery. All subscriptions to the same run/event are consumed together.
        for wait in payload.get('execution_waits',{}).values():
            if not wait.get('seq') or wait.get('interrupted'):continue
            for proposal in conn.execute("SELECT id,receipt_json FROM conversation_proposals WHERE state='applied' AND json_extract(receipt_json,'$.work_id')=? AND json_extract(receipt_json,'$.run_id')=?",(wait['work_id'],wait['run_id'])).fetchall():
                receipt=json.loads(proposal['receipt_json'])
                if '_result_delivery' not in receipt:continue
                receipt['_result_delivery']['seen_seq']=max(receipt['_result_delivery']['seen_seq'],wait['seq'])
                conn.execute('UPDATE conversation_proposals SET receipt_json=? WHERE id=?',(encode(receipt),proposal['id']))

    def reserve_next(self):
        """Atomically claim one new outcome; active user turns have priority."""
        with self.service.store.transaction() as conn:
            for record in conn.execute("SELECT t.*,s.ui_session,s.revoked_at FROM conversation_turns t JOIN conversation_segments s ON s.id=t.segment_id WHERE json_extract(t.payload_json,'$.origin')='task_result' AND t.state='reserved' AND s.revoked_at IS NULL ORDER BY t.created_at,t.id").fetchall():
                segment = self.bridge.conversations.segment(conn, record['ui_session'])
                payload = json.loads(record['payload_json'])
                if not payload.get('session_key','').startswith('agent:main:easel-pipeline:'):continue
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
                origin=conn.execute('SELECT payload_json FROM conversation_turns WHERE segment_id=? ORDER BY created_at DESC,id DESC LIMIT 1',(segment['id'],)).fetchone()
                if not origin or not json.loads(origin[0]).get('session_key','').startswith('agent:main:easel-pipeline:'):continue
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
                if conn.execute("SELECT 1 FROM conversation_turns t JOIN conversation_segments s ON s.id=t.segment_id WHERE s.ui_session=? AND (t.state IN ('reserved','dispatching','active','unknown') OR (json_extract(t.payload_json,'$.delivery_state')='streaming' AND json_extract(t.payload_json,'$.delivery_lease_until')>?))", (segment['ui_session'],time.time())).fetchone():
                    continue
                turn_id = 'result_' + digest([segment['id'],run['id'],event['seq']])[:48]
                receipt['_result_delivery']['seen_seq'] = event['seq']
                conn.execute('UPDATE conversation_proposals SET receipt_json=? WHERE id=?', (encode(receipt),proposal['id']))
                if conn.execute('SELECT 1 FROM conversation_turns WHERE id=?',(turn_id,)).fetchone():
                    continue
                from .conversation_pipeline import pending
                context = pending(self.bridge.conversations, conn, segment)
                snapshot = context['work']
                result_event = self.event_result(conn, snapshot, run, event)
                from .conversation_pipeline import turn_context
                prompt = '' if result_event['outcome']=='blocked' else self.build_prompt(turn_context(context), result_event)
                payload = {'origin':'task_result','message':None,'attachments':[], 'result_event':result_event,
                    'work_id':work['id'],'revision':work['revision'], 'session_key':'agent:main:easel-pipeline:'+segment['id'],
                    'native_session_id':segment['native_session_id'],'run_id':None,'tickets':{},'results':{},'calls':{},'answer':'',
                    'visible_proposals':[p['id'] for p in context['pending']], 'prompt_hash':hashlib.sha256(prompt.encode()).hexdigest(), 'result_prompt':prompt}
                conn.execute('INSERT INTO conversation_turns VALUES (?,?,?,?,?,?)',(turn_id,segment['id'],digest(result_event),encode(payload),'reserved',now()))
                return self._dispatch(conn,turn_id,segment['ui_session'],payload)
        return None

    @staticmethod
    def build_prompt(context, result_event):
        return ('【宿主任务结果事件，不是用户新指令或授权】\n'+encode(result_event)+
                    '\n请接续当前创作对话。先读取真实结果；方案成功时展示摘要、完整逐字脚本和分镜，必须先用easel_pipeline offer action=confirm创建本版待确认提案（含素材、配音及剪辑/检查实际需要的模型服务），然后展示返回的范围并提出制作确认问题；剪辑制作或局部修订完成时交付实际视频，按outputs.checks分别说明技术、抽帧视觉、完整语义和声音检查；manual_review_required表示待人工审阅，不单凭needs_fix推断存在缺陷；按输出delivery.message提示后续动作，等待反馈，不自动新建提案或代签。失败时结合material_summary一次解释全部已知缺口、已完成部分、保留成果、可行下一步和新增调用费用风险；候选不等于审查通过，用户无需复制内部编号。UNKNOWN不得声称自动核实或重新派发，明确当前接口能否查询。不得把本事件当作用户同意，不得自行恢复、改稿、授权或制作。视频用返回的playback_url嵌入<video controls src="...">，不得臆造地址。\n【服务端当前上下文】\n'+encode(context))

    @staticmethod
    def _dispatch(conn,turn_id,session,payload):
        event = payload.get('result_event', {})
        answer = output_text(event)
        if event.get('outcome') == 'blocked':
            answer = failure_text(event['tasks'], event['run_state'], unknown=bool(event.get('unknown_operations')))
        if answer is not None:
            # Persist known outcomes through the existing local delivery channel.
            payload.update(answer=answer, delivery_state='delivered', delivery_lease_until=0)
            conn.execute("UPDATE conversation_turns SET state='ended',payload_json=? WHERE id=?",(encode(payload),turn_id))
            return {'turn_id':turn_id,'ui_session':session,'payload':payload,'local_delivery':True,'answer':answer}
        conn.execute("UPDATE conversation_turns SET state='dispatching' WHERE id=?",(turn_id,))
        return {'turn_id':turn_id,'ui_session':session,'prompt':payload['result_prompt'],'payload':payload}
