import { useEffect, useState, useCallback, useRef } from 'react';
import { videoRequest, type ConversationView } from '../lib/conversationApi';
import type { ChatMessage } from '../lib/store';

export default function VideoConversation({sessionId,segmentId,onBound,onBindingPending,onRestore}: {sessionId:string;segmentId?:string;persona?:string;onRestore:(messages:ChatMessage[])=>void;onBound:(id:string)=>void;onDraft:(text:string)=>void;onBindingPending:(pending:boolean)=>void}) {
  const [view,setView]=useState<ConversationView|null>(null);
  const [error,setError]=useState('');
  const sequence=useRef(0);
  const restore=useRef(onRestore);restore.current=onRestore;
  const pending=useRef(onBindingPending);pending.current=onBindingPending;
  const load=useCallback(async(isCurrent:()=>boolean=()=>true)=>{
    const request=++sequence.current;
    try {
      const next=await videoRequest<ConversationView>(encodeURIComponent(sessionId));
      if(request!==sequence.current||!isCurrent())return;
      setView(next);setError('');
      restore.current(next.result_messages || []);
      pending.current((next.result_messages || []).some(m=>['reserved','dispatching','active'].includes(m.resultState || '')));
      if(next.segment_id!==segmentId)onBound(next.segment_id);
    } catch(e) { if(request===sequence.current&&isCurrent())setError((e as Error).message); }
  },[sessionId,segmentId,onBound]);
  useEffect(()=>{let active=true;void load(()=>active);const poll=setInterval(()=>void load(()=>active),2500);return()=>{active=false;clearInterval(poll);};},[load]);
  useEffect(()=>()=>pending.current(false),[]);
  const kind=view?.context.kind;
  const channelFlow=kind==='channel_create',directorFlow=kind==='director_formation';
  return <section className="video-conversation" aria-label={channelFlow?'频道设置对话':directorFlow?'导演设置对话':'视频创作对话'}>
    {error&&<p role="alert">{error}</p>}
  </section>;
}
