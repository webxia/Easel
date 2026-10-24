import { productionRequest,productionURL } from './productionApi';
export interface PublicationCover {digest:string;width:number;height:number}
export const publicationCoverURL=(id:string,checksum:string)=>productionURL(`publications/${encodeURIComponent(id)}/covers/${encodeURIComponent(checksum)}`);
export interface PublicationContent {cover?:PublicationCover|null;title:string;body:string;tags:string[];tid:number;copyright:number;source:string;credits:string;action:string;account:{platform:string;uid:string;name:string}|null}
export interface Publication {platform?:string;last_error?:{message?:string};id:string;work_id:string;output_id:string;output_revision:number;revision:number;state:string;content:PublicationContent;confirmation_hash:string;attempts:{id:string;state:string;receipt:{execution?:{returncode:number|null;timed_out:boolean;response_codes?:number[];remote_id?:string;last_stage?:string;error_kinds?:string[]};outcome?:string;reason?:string;url?:string;matched?:{status:string;platform_content_id:string}}}[]}
export const publicationCall=<T>(path:string,body?:unknown,method='POST')=>productionRequest<T>(`publications${path}`,body===undefined&&method==='GET'?undefined:{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
export async function openPublication(work_id:string,output_id:string) {
 openPublishSource(work_id,output_id);
}
export function publicationStatus(draft:Publication):string {
 const last=draft.attempts.at(-1);
 if(!last)return draft.state==='cancelled'?'草稿已取消':'本地草稿 · 尚未投稿';
 if(last.state==='verified')return `平台已核实：${last.receipt.matched?.status||'状态待查询'}`;
 if(last.state==='sending')return '正在执行投稿 · 尚未确认结果';
 if(last.state==='failed_before_submit')return '尚未投稿 · 可修改后重新确认';
 if(last.receipt.execution?.remote_id)return `已提交${!draft.platform||draft.platform==='bilibili'?'B站':'平台'} · 平台状态待核实`;
 return '投稿结果待核实 · 不会重复上传';
}

export function publicationIdFromHash(hash:string):string|undefined {
 const match=/^#publication=([a-zA-Z0-9_-]+)$/.exec(hash);
 return match?.[1];
}
export function openPublicationDraft(id:string) {
 if(!/^[a-zA-Z0-9_-]+$/.test(id))return;
 window.history.replaceState(null,'',`#publication=${id}`);
 window.dispatchEvent(new CustomEvent('easel:publication',{detail:id}));
}

export function publicationGuidance(draft:Publication):string {
 const last=draft.attempts.at(-1);
 if(!last)return draft.state==='cancelled'?'草稿已取消。可从内容库的已接受版本重新打开。':'保存文案与实际账号后，查看最终内容并确认投稿。';
 if(last.state==='verified')return '已找到对应平台稿件，请按平台返回的审核或公开状态查看结果。';
 if(last.state==='sending')return '当前正在执行上传或平台查询，尚未确认文件上传和投稿成功。刷新后可继续查看原记录，不要再次提交。';
 if(last.state==='failed_before_submit')return '已核实本片未投稿，历史尝试保留。请核对原草稿并重新查看最终确认。';
 if(last.receipt.execution?.remote_id)return `${!draft.platform||draft.platform==='bilibili'?'B站':'平台'}已返回稿件编号，请仅核实原稿件的审核或公开状态，不要重复投稿。`;
 if(!last.receipt.execution)return '尚未核实投稿成功。这次历史执行缺少上传工具退出回执，无法确定是否已上传；可仅核实原投稿或查看平台稿件管理，不会重复上传。';
 return last.receipt.reason||'上传工具已返回，但平台结果尚未确认。请仅核实原投稿，不要重复上传。';
}

export function sessionRestorePage(hash:string,hasVideo:boolean):'publish'|'chat'|undefined {
 return (publicationIdFromHash(hash)||publishSourceFromHash(hash))?'publish':hasVideo?'chat':undefined;
}

export function publicationExecutionText(execution:NonNullable<Publication['attempts'][number]['receipt']['execution']>):string {
 const stages:Record<string,string>={upload_preparing:'正在准备上传',pre_upload:'已进入文件上传准备',upload_complete:'文件已上传完成',submit_acknowledged:'投稿接口已返回成功回执'};
 const errors:Record<string,string>={tls_error:'上传连接的证书校验失败',certificate_expired:'上传线路证书已过期',network_timeout:'网络请求超时',connection_error:'网络连接失败',dns_error:'域名解析失败'};
 const details=[execution.last_stage&&stages[execution.last_stage],...(execution.error_kinds||[]).map(k=>errors[k]).filter(Boolean)].filter(Boolean);
 return details.length?details.join('；')+'。':'';
}

export interface PublishSource {work_id:string;output_id:string}
export function publishSourceFromHash(hash:string):PublishSource|undefined {
 const m=/^#publish-work=([a-zA-Z0-9_-]+)&output=([a-zA-Z0-9_-]+)$/.exec(hash);
 return m?{work_id:m[1],output_id:m[2]}:undefined;
}
export function openPublishSource(work_id:string,output_id:string){
 if(!/^[a-zA-Z0-9_-]+$/.test(work_id)||!/^[a-zA-Z0-9_-]+$/.test(output_id))return;
 window.history.replaceState(null,'',`#publish-work=${work_id}&output=${output_id}`);
 window.dispatchEvent(new CustomEvent('easel:publish-source',{detail:{work_id,output_id}}));
}
export const fileCoverURL=(checksum?:string)=>productionURL('').replace(/production\/$/,'publish/covers')+(checksum?`/${checksum}`:'');
export async function fileCoverCall<T>(suffix:string,body:unknown,upload=false):Promise<T>{
 const res=await fetch(fileCoverURL()+suffix,{method:'POST',...(upload?{body:body as FormData}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});
 const data=await res.json();if(!res.ok)throw new Error(data.error?.user_message||data.detail||'封面处理失败');return data;
}
