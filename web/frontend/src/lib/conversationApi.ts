import { productionCommand, type Json } from './productionApi';
export interface VideoEntry extends Json { kind?: string; profile_ref?: string; channel_id?: string; director_revision?: string; director_trial?: boolean; work_id?: string; output_id?: string }
export interface Proposal { id:string; kind:string; body_hash:string; state:string; body:{ values:Json; source_refs:string[]; target:Json; work_id?:string; work_revision?:number }; receipt?:Json }
export interface ConversationView { segment_id:string; work_id?:string; context:VideoEntry & {channel?:{name:string;revision:number}}; proposals:Proposal[]; messages:{role:'user'|'assistant';content:string}[]; turns:{id:string;state:string}[] }
const root=window.location.pathname.replace(/\/index\.html$/, '').replace(/\/$/, '');
export async function videoRequest<T>(path:string, method='GET', body?:unknown):Promise<T> {
  const response=await fetch(`${root}/api/chat/video/${path}`,{method,cache:'no-store',headers:{'Content-Type':'application/json'},...(body ? {body:JSON.stringify(body)} : {})});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error?.user_message || data.detail || '创作对话暂不可用');
  return data;
}
/** Retain identity across refresh, response loss and double clicks. Scope includes exact target/version/payload. */
export function actionId(scope:string, payload:unknown):string {
  const key=`easel_action:${scope}:${JSON.stringify(payload)}`;
  let value=localStorage.getItem(key);
  if(!value){value=crypto.randomUUID();localStorage.setItem(key,value);}
  return value;
}
export function enterVideo(session:string,entry:VideoEntry) {
  // Navigation must select the segment again after visiting another entry.
  // A permanent actionId would replay an old receipt without selecting it.
  // enter itself reuses matching segments and never creates a Work or Run.
  return videoRequest<{segment_id:string;work_id?:string}>(`${encodeURIComponent(session)}/enter`,'POST',{command_id:crypto.randomUUID(),entry});
}
export function applyProposal(session:string,p:Proposal,dismiss=false) {
  return videoRequest(`${encodeURIComponent(session)}/proposals/${p.id}/apply`,'POST',{command_id:actionId(p.id,{hash:p.body_hash,dismiss}),hash:p.body_hash,dismiss});
}
export function workCommand<T={work_id?:string;revision:number}>(workId:string,revision:number,path:string,payload:Json,method='POST'):Promise<T> {
  return productionCommand(`works/${workId}/${path}`,payload,revision,method,actionId(`work:${workId}:${path}`,{revision,payload}));
}
export function catalogCommand<T={id:string;revision:number}>(path:string,revision:number,payload:Json,method='POST'):Promise<T> {
  return productionCommand(path,payload,revision,method,actionId(path,{revision,payload}));
}
