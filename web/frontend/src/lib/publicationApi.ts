import { productionRequest } from './productionApi';
export interface PublicationContent {title:string;body:string;tags:string[];tid:number;copyright:number;source:string;credits:string;action:string;account:{platform:string;uid:string;name:string}|null}
export interface Publication {last_error?:{message?:string};id:string;work_id:string;output_id:string;output_revision:number;revision:number;state:string;content:PublicationContent;confirmation_hash:string;attempts:{id:string;state:string;receipt:{outcome?:string;reason?:string;url?:string;matched?:{status:string;platform_content_id:string}}}[]}
export const publicationCall=<T>(path:string,body?:unknown,method='POST')=>productionRequest<T>(`publications${path}`,body===undefined&&method==='GET'?undefined:{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
export async function openPublication(work_id:string,output_id:string) {
 const draft=await publicationCall<Publication>('/prepare',{work_id,output_id});
 window.dispatchEvent(new CustomEvent('easel:publication',{detail:draft.id}));
}
export function publicationStatus(draft:Publication):string {
 const last=draft.attempts.at(-1);
 if(!last)return draft.state==='cancelled'?'草稿已取消':'本地草稿 · 尚未投稿';
 if(last.state==='verified')return `平台已核实：${last.receipt.matched?.status||'状态待查询'}`;
 if(last.state==='failed_before_submit')return '尚未投稿 · 可修改后重新确认';
 return '投稿结果待核实 · 不会重复上传';
}
