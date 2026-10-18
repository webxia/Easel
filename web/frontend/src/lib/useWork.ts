import { useState, useEffect } from 'react';
import { productionRequest, newerSnapshot, type Work } from './productionApi';

export function useWork(id?:string) {
  const [work,setWork]=useState<Work|null>(null);const [error,setError]=useState('');const [connected,setConnected]=useState(false);
  useEffect(()=>{
    setWork(null);setError('');if(!id)return;
    let disposed=false;let busy=false;const controller=new AbortController();
    const refresh=async()=>{if(busy)return;busy=true;try{const snapshot=await productionRequest<Work>(`works/${id}`,{signal:controller.signal});if(!disposed){setWork(w=>newerSnapshot(w,snapshot,id));setError('');}}catch(e){if(!disposed)setError((e as Error).message);}finally{busy=false;}};
    void refresh();
    // Named Work SSE, independent from chat done; cursor is carried by EventSource reconnect.
    const source=new EventSource(`${window.location.pathname.replace(/\/index\.html$/, '').replace(/\/$/, '')}/api/production/works/${id}/events`);
    source.onopen=()=>setConnected(true);source.onerror=()=>{setConnected(false);void refresh();};
    const events=['snapshot','command_accepted','input_registered','brief_updated','task_started','task_completed','task_succeeded','task_failed','task_waiting_external','task_retryable_failed','task_needs_decision','run_claimed','run_superseded','quality_repair_requested','render_cancel_observed','render_preserved','artifact_registered','artifact_created','render_progress','operation_reserved','operation_sending','operation_observed','operation_waiting','decision_required','revision_created','quality_result','quality_checked','quality_progress','revision_proposed','run_completed','run_cancelled','plan_created','director_analyzed','output_accepted','settings_saved','decision_resolved'];
    for(const kind of events)source.addEventListener(kind,()=>void refresh());
    const interval=setInterval(()=>void refresh(),5000);
    return()=>{disposed=true;controller.abort();source.close();clearInterval(interval);};
  },[id]);
  return {work,error,connected};
}
