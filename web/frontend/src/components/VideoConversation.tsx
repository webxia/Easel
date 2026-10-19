import { useEffect, useState, useCallback, useRef } from 'react';
import { enterVideo, videoRequest, type ConversationView, type VideoEntry } from '../lib/conversationApi';
import { productionRequest, workLabels, type Work, type Director } from '../lib/productionApi';
import WorkCards from './WorkCards';

const labels:Record<string,string>={draft:'作品草稿',plan:'整理完整方案',revision:'修改指定成片',channel_create:'保存新频道',channel_defaults:'保存频道修改',director_formation:'分析参考并形成导演',director_revision:'保存导演风格版本',pipeline:'管线待答事项'};

export default function VideoConversation({sessionId,segmentId,onBound,onBindingPending,onRestore}: {sessionId:string;segmentId?:string;persona?:string;onRestore:(messages:{role:'user'|'assistant';content:string}[])=>void;onBound:(id:string)=>void;onDraft:(text:string)=>void;onBindingPending:(pending:boolean)=>void}) {
  const [view,setView]=useState<ConversationView|null>(null);
  const [work,setWork]=useState<Work|null>(null);
  const [directors,setDirectors]=useState<Director[]>([]);
  const [error,setError]=useState('');
  const sequence=useRef(0);
  const load=useCallback(async(isCurrent:()=>boolean=()=>true)=>{
    const request=++sequence.current;
    try {
      const next=await videoRequest<ConversationView>(encodeURIComponent(sessionId));
      const [snapshot,catalog]=await Promise.all([
        next.work_id?productionRequest<Work>(`works/${next.work_id}`):Promise.resolve(null),
        productionRequest<Director[]>('directors'),
      ]);
      if(request!==sequence.current||!isCurrent())return;
      setView(next);setWork(snapshot);setDirectors(catalog);setError('');
      if(next.segment_id!==segmentId)onBound(next.segment_id);
    } catch(e) { if(request===sequence.current&&isCurrent())setError((e as Error).message); }
  },[sessionId,segmentId,onBound]);
  useEffect(()=>{let active=true;void load(()=>active);const poll=setInterval(()=>void load(()=>active),2500);return()=>{active=false;clearInterval(poll);};},[load]);
  // Choosing a target is a conversational task, never a form that blocks send.
  useEffect(()=>{onBindingPending(false);return()=>onBindingPending(false);},[onBindingPending]);
  const enter=async(entry:VideoEntry)=>{try{const result=await enterVideo(sessionId,entry);onBound(result.segment_id);await load();}catch(e){setError((e as Error).message);}};
  const kind=view?.context.kind;
  const channelFlow=kind==='channel_create',directorFlow=kind==='director_formation';
  const selected=String(((work?.settings||view?.context.settings) as Record<string,unknown>|undefined)?.director_revision||'');
  const director=directors.flatMap(d=>d.versions.map(v=>({name:d.name,...v}))).find(v=>v.id===selected);
  return <section className="video-conversation" aria-label={channelFlow?'频道设置对话':directorFlow?'导演设置对话':'视频创作对话'}>
    {error&&<p role="alert">{error}</p>}
    {view&&<>
      <p className="creation-help">{channelFlow?'频道管线':directorFlow?'导演管线':'视频创作管线'} · {String(view.context.profile_name||'当前画像')}
        {view.context.channel?.name?` · ${view.context.channel.name}`:!channelFlow?' · 频道待选择':''}
        {director?` · ${director.name} v${director.revision}${director.accepted_at?'':'（待试片）'}`:!channelFlow?' · 导演待选择':''}</p>
      <p className="creation-help">直接在对话里选择、修改或确认，Easel 会根据当前步骤继续；缺少的信息会在对话中询问。</p>
      <details><summary>本段讨论与操作记录</summary>
        <button className="btn btn-ghost" onClick={()=>onRestore(view.messages)}>恢复本段讨论</button>
        {view.proposals.filter(p=>p.state==='proposed'||p.state==='applied').map(p=><article className="work-card" key={p.id}>
          <h3>{labels[p.kind]||p.kind} · {p.state==='applied'?'已执行':'待对话确认'}</h3>
          <p>{String(p.body.values.summary||'请在对话中说明是否采用，也可以继续提出修改。')}</p>
          <details><summary>查看具体内容</summary><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify(p.body.values,null,2)}</pre></details>
        </article>)}
      </details>
      {view.work_id&&!channelFlow&&<details open={!!work&&['awaiting_confirmation','needs_decision','reviewable','preview_needs_fix'].includes(work.state)}>
        <summary>{directorFlow?'参考与分析进度':`方案、进度与审片 · ${work?workLabels[work.state]||work.state:'正在读取'}`}</summary>
        <WorkCards conversationOnly referenceOnly={directorFlow} key={view.work_id} workId={view.work_id} sessionId={sessionId} onChanged={()=>void load()} onContinue={entry=>void enter(entry)}/>
      </details>}
    </>}
  </section>;
}
