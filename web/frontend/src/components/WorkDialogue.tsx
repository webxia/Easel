import { useWork } from '../lib/useWork';
import { workDialogue } from '../lib/workDialogue';
import { artifactURL } from '../lib/productionApi';
import MessageBubble from './MessageBubble';

/** Live dialogue results recover from the Work snapshot, without duplicate chat writes. */
export default function WorkDialogue({workId,referenceOnly=false,onDraft}:{workId:string;referenceOnly?:boolean;onDraft:(text:string)=>void}) {
  const {work,error}=useWork(workId);
  if(!work)return error?<p role="alert">{error}</p>:null;
  const {status,reply,plan,outputs}=workDialogue(work,referenceOnly);
  return <div aria-label="创作对话结果">
    {error&&<p role="alert">暂时无法更新制作结果：{error}</p>}
    {status&&<div role="status"><MessageBubble message={{role:'assistant',content:status}}/>
      {reply&&<button onClick={()=>onDraft(reply)}>讨论如何继续</button>}
    </div>}
    {plan&&<div key={`plan-${plan.revision}`}>
      <MessageBubble message={{role:'assistant',content:`完整方案 · 版本 ${plan.revision}${plan.confirmed_at?'（已确认）':''}\n\n${plan.plan.summary}\n\n### 完整逐字脚本\n\n${plan.plan.script}\n\n### 分镜\n\n${plan.plan.scenes.map((s,i)=>`**${i+1}. ${s.purpose}**\n\n画面：${s.visual}\n\n旁白：${s.narration}`).join('\n\n')}\n\n${plan.confirmed_at?'已按此方案提交制作。':'请直接回复修改意见，或让我列出本版制作所需的服务和额度供你确认。'}`}}/>
      {!plan.confirmed_at&&<button onClick={()=>onDraft(`我已查看方案版本 ${plan.revision}，请列出制作所需服务和额度供我确认。`)}>讨论本版制作</button>}
    </div>}
    {outputs.map(o=><div key={o.id} className="message-row assistant"><div className="msg-col assistant">
      <MessageBubble message={{role:'assistant',content:`视频版本 ${o.output_revision}${work.accepted_output_id===o.id?' · 已接受':''}\n\n${o.manual_review_required?'技术检查通过；仍需人工完整审片，不能视为自动语义检查通过。':o.quality_state==='passed'?'检查通过，可以审阅。':'这是待核实或待修的预览，尚不能当作检查通过的成片。'}\n\n请观看后直接在对话中提出修改意见。`}}/>
      <video controls preload="metadata" src={artifactURL(o.id)} style={{width:'100%',maxHeight:440}}/>
      <a href={artifactURL(o.export_artifact_id||o.id)} download>下载视频与署名</a>
      <button onClick={()=>onDraft(`关于视频版本 ${o.output_revision}，我的修改意见是：`)}>反馈此版本</button>
    </div></div>)}
  </div>;
}
