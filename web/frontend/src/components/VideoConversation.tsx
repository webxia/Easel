import { useEffect, useState, useCallback, useRef } from 'react';
import { videoRequest, type ConversationView } from '../lib/conversationApi';
import WorkDialogue from './WorkDialogue';

export default function VideoConversation({sessionId,segmentId,onBound,onBindingPending,onDraft}: {sessionId:string;segmentId?:string;persona?:string;onRestore:(messages:{role:'user'|'assistant';content:string}[])=>void;onBound:(id:string)=>void;onDraft:(text:string)=>void;onBindingPending:(pending:boolean)=>void}) {
  const [view,setView]=useState<ConversationView|null>(null);
  const [error,setError]=useState('');
  const sequence=useRef(0);
  const load=useCallback(async(isCurrent:()=>boolean=()=>true)=>{
    const request=++sequence.current;
    try {
      const next=await videoRequest<ConversationView>(encodeURIComponent(sessionId));
      if(request!==sequence.current||!isCurrent())return;
      setView(next);setError('');
      if(next.segment_id!==segmentId)onBound(next.segment_id);
    } catch(e) { if(request===sequence.current&&isCurrent())setError((e as Error).message); }
  },[sessionId,segmentId,onBound]);
  useEffect(()=>{let active=true;void load(()=>active);const poll=setInterval(()=>void load(()=>active),2500);return()=>{active=false;clearInterval(poll);};},[load]);
  // Choosing a target is a conversational task, never a form that blocks send.
  useEffect(()=>{onBindingPending(false);return()=>onBindingPending(false);},[onBindingPending]);
  const kind=view?.context.kind;
  const channelFlow=kind==='channel_create',directorFlow=kind==='director_formation';
  return <section className="video-conversation" aria-label={channelFlow?'频道设置对话':directorFlow?'导演设置对话':'视频创作对话'}>
    {error&&<p role="alert">{error}</p>}
    {view&&<>
      {view.work_id&&!channelFlow&&
        <WorkDialogue referenceOnly={directorFlow} key={view.work_id} workId={view.work_id} onDraft={onDraft}/>
      }
    </>}
  </section>;
}
