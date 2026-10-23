import {useEffect,useState} from 'react';
import {artifactURL} from '../lib/productionApi';
import {publicationCall,publicationStatus,type Publication,type PublicationContent} from '../lib/publicationApi';

export default function AcceptedPublication({selectedId}:{selectedId?:string}) {
 const [drafts,setDrafts]=useState<Publication[]>([]);const [draft,setDraft]=useState<Publication|null>(null);
 const [content,setContent]=useState<PublicationContent|null>(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 const refresh=async()=>setDrafts(await publicationCall<Publication[]>('',undefined,'GET'));
 const select=(d:Publication)=>{setDraft(d);setContent(structuredClone(d.content));};
 useEffect(()=>{void refresh().catch(e=>setError(e.message));},[]);
 useEffect(()=>{if(selectedId)void publicationCall<Publication>(`/${selectedId}`,undefined,'GET').then(select).catch(e=>setError(e.message));},[selectedId]);
 const run=async(action:()=>Promise<void>)=>{if(busy)return;setBusy(true);setError('');try{await action();await refresh();}catch(e){setError((e as Error).message+'。请读取原记录核实，不要重复提交。');}finally{setBusy(false);}};
 const dirty=!!draft&&JSON.stringify(content)!==JSON.stringify(draft.content);
 const editable=draft?.state==='draft';
 const update=(patch:Partial<PublicationContent>)=>setContent(c=>c?{...c,...patch}:c);
 const submit=()=>run(async()=>{
  if(!draft||dirty)return;
  const c=draft.content;
  if(!window.confirm(`确认向B站投稿：\n账号：${c.account?.name}（UID ${c.account?.uid}）\n成片版本：${draft.output_revision}\n标题：${c.title}\n正文：${c.body}\n署名：${c.credits||'无'}\n标签：${c.tags.join('、')}\n分区ID：${c.tid}；${c.copyright===1?'自制':'转载：'+c.source}\n平台审核通过后可公开。此操作会真实上传和投稿。`))return;
  select(await publicationCall<Publication>(`/${draft.id}/submit`,{revision:draft.revision,confirmation_hash:draft.confirmation_hash}));
 });
 return <section className="panel" aria-label="已接受成片发布"><h2>已接受成片 · B站投稿</h2><p>选定具体接受版后保存草稿，最终确认才会投稿。账号登录仍在原账号页完成。</p>
 <button disabled={busy} onClick={()=>void run(async()=>{await refresh();if(draft)select(await publicationCall<Publication>(`/${draft.id}`,undefined,'GET'));})}>刷新原记录</button>
 {error&&<p role="alert">{error}</p>}
 <ul>{drafts.map(d=><li key={d.id}><button disabled={busy} onClick={()=>select(d)}>{d.content.title} · 版本{d.output_revision} · {publicationStatus(d)}</button></li>)}</ul>
 {draft&&content&&<div><h3>成片版本{draft.output_revision} · {publicationStatus(draft)}</h3><video controls preload="metadata" src={artifactURL(draft.output_id)} style={{width:'100%',maxHeight:300}}/>
 {draft.last_error?.message&&<p role="alert">尚未投稿：{draft.last_error.message}</p>}
 <fieldset disabled={busy||!editable}><label>标题<input className="field" value={content.title} onChange={e=>update({title:e.target.value})}/></label>
 <label>正文<textarea className="field" value={content.body} onChange={e=>update({body:e.target.value})}/></label>
 <label>标签（逗号分隔）<input className="field" value={content.tags.join(',')} onChange={e=>update({tags:e.target.value.split(/[,，]/)})}/></label>
 <label>分区ID<input type="number" value={content.tid} onChange={e=>update({tid:Number(e.target.value)})}/></label>
 <label>稿件类型<select value={content.copyright} onChange={e=>update({copyright:Number(e.target.value)})}><option value={1}>自制</option><option value={2}>转载</option></select></label>
 {content.copyright===2&&<label>转载来源<input className="field" value={content.source} onChange={e=>update({source:e.target.value})}/></label>}
 <p>素材署名（随正文提交）：{content.credits||'无附加署名'}</p>
 <p>目标账号：{content.account?`${content.account.name} · UID ${content.account.uid}`:'尚未读取'}</p>
 <button onClick={()=>void run(async()=>update({account:await publicationCall<PublicationContent['account']>('/account')}))}>读取实际登录账号</button>
 <button onClick={()=>void run(async()=>select(await publicationCall<Publication>(`/${draft.id}`,{revision:draft.revision,content},'PUT')))}>保存草稿</button>
 <button disabled={dirty||!content.account} onClick={()=>void submit()}>查看最终确认并投稿</button>
 <button onClick={()=>void run(async()=>select(await publicationCall<Publication>(`/${draft.id}/cancel`,{revision:draft.revision})))}>取消未提交草稿</button>
 </fieldset>
 {dirty&&<p>内容已修改，请先保存，再核对最终确认。</p>}
 {draft.attempts.map(a=><p key={a.id}>投稿记录：{a.state==='verified'?a.receipt.matched?.status:'待核实'} {a.receipt.reason}{a.receipt.url&&<a href={a.receipt.url} target="_blank" rel="noreferrer">查看平台稿件</a>}</p>)}
 {draft.attempts.length>0&&<button disabled={busy} onClick={()=>void run(async()=>select(await publicationCall<Publication>(`/${draft.id}/reconcile`)))}>仅核实原投稿结果</button>}
 </div>}
 </section>;
}
