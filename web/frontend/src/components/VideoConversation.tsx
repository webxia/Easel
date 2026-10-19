import { useEffect, useState, useCallback, useRef } from 'react';
import { enterVideo, videoRequest, type ConversationView, type VideoEntry } from '../lib/conversationApi';
import { productionRequest, workLabels, type Work } from '../lib/productionApi';
import WorkCards from './WorkCards';

export default function VideoConversation({sessionId,segmentId,onBound,onBindingPending}: {sessionId:string;segmentId?:string;persona?:string;onRestore:(messages:{role:'user'|'assistant';content:string}[])=>void;onBound:(id:string)=>void;onDraft:(text:string)=>void;onBindingPending:(pending:boolean)=>void}) {
  const [view,setView]=useState<ConversationView|null>(null);
  const [work,setWork]=useState<Work|null>(null);
  const [error,setError]=useState('');
  const sequence=useRef(0);
  const load=useCallback(async(isCurrent:()=>boolean=()=>true)=>{
    const request=++sequence.current;
    try {
      const next=await videoRequest<ConversationView>(encodeURIComponent(sessionId));
      const snapshot=next.work_id?await productionRequest<Work>(`works/${next.work_id}`):null;
      if(request!==sequence.current||!isCurrent())return;
      setView(next);setWork(snapshot);setError('');
      if(next.segment_id!==segmentId)onBound(next.segment_id);
    } catch(e) { if(request===sequence.current&&isCurrent())setError((e as Error).message); }
  },[sessionId,segmentId,onBound]);
  useEffect(()=>{let active=true;void load(()=>active);const poll=setInterval(()=>void load(()=>active),2500);return()=>{active=false;clearInterval(poll);};},[load]);
  // Choosing a target is a conversational task, never a form that blocks send.
  useEffect(()=>{onBindingPending(false);return()=>onBindingPending(false);},[onBindingPending]);
  const enter=async(entry:VideoEntry)=>{try{const result=await enterVideo(sessionId,entry);onBound(result.segment_id);await load();}catch(e){setError((e as Error).message);}};
  const kind=view?.context.kind;
  const channelFlow=kind==='channel_create',directorFlow=kind==='director_formation';
  return <section className="video-conversation" aria-label={channelFlow?'频道设置对话':directorFlow?'导演设置对话':'视频创作对话'}>
    {error&&<p role="alert">{error}</p>}
    {view&&<>
      {view.work_id&&!channelFlow&&<details open={!!work&&['awaiting_confirmation','needs_decision','reviewable','preview_needs_fix'].includes(work.state)}>
        <summary>{directorFlow?'参考与分析进度':`方案、进度与审片 · ${work?workLabels[work.state]||work.state:'正在读取'}`}</summary>
        <WorkCards conversationOnly referenceOnly={directorFlow} key={view.work_id} workId={view.work_id} sessionId={sessionId} onChanged={()=>void load()} onContinue={entry=>void enter(entry)}/>
      </details>}
    </>}
  </section>;
}
