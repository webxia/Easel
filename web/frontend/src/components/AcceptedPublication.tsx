import BilibiliPartition from './BilibiliPartition';
import {useBilibiliPartitions,partitionLabel} from '../lib/bilibiliPartitions';
import {useEffect,useState} from 'react';
import {artifactURL} from '../lib/productionApi';
import {openPublishSource,publicationCall,publicationStatus,publicationGuidance,publicationExecutionText,publicationCoverURL,type Publication,type PublicationContent} from '../lib/publicationApi';
import PublicationCover from './PublicationCover';
import {IconPublish,IconRefresh} from './icons';

export default function AcceptedPublication({selectedId}:{selectedId?:string}) {
 const [drafts,setDrafts]=useState<Publication[]>([]),[draft,setDraft]=useState<Publication|null>(null);
 const [content,setContent]=useState<PublicationContent|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [confirming,setConfirming]=useState<'submit'|'resolve'|null>(null);
 const refresh=async()=>setDrafts(await publicationCall<Publication[]>('',undefined,'GET'));
 const select=(d:Publication)=>{setDraft(d);setContent(structuredClone(d.content));setConfirming(null);};
 useEffect(()=>{void refresh().catch(e=>setError(e.message));},[]);
 useEffect(()=>{if(selectedId)void publicationCall<Publication>(`/${selectedId}`,undefined,'GET').then(select).catch(e=>setError(e.message));},[selectedId]);
 const run=async(action:()=>Promise<void>)=>{if(busy)return;setBusy(true);setError('');try{await action();await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
 const dirty=!!draft&&JSON.stringify(content)!==JSON.stringify(draft.content);
 const editable=draft?.state==='draft';
 const update=(patch:Partial<PublicationContent>)=>setContent(c=>c?{...c,...patch}:c);
 const latest=draft?.attempts.at(-1);
 const platform=draft?.platform||'bilibili';
 const partitions=useBilibiliPartitions(!!draft&&platform==='bilibili');
 const label=({bilibili:'B站',douyin:'抖音',xiaohongshu:'小红书',kuaishou:'快手','weixin-channels':'视频号'} as Record<string,string>)[platform]||platform;
 const submit=()=>run(async()=>{
  if(!draft||dirty||confirming!=='submit')return;
  setConfirming(null);
  select(await publicationCall<Publication>(`/${draft.id}/submit`,{revision:draft.revision,confirmation_hash:draft.confirmation_hash}));
 });
 const resolveAbsent=()=>run(async()=>{
  if(!draft||!latest||confirming!=='resolve')return;
  setConfirming(null);
  select(await publicationCall<Publication>(`/${draft.id}/resolve-absent`,{revision:draft.revision,confirmation_hash:draft.confirmation_hash,attempt_id:latest.id,confirmed_absent:true}));
 });
 // Observing an in-flight attempt after refresh never calls submit again.
 useEffect(()=>{
  if(!draft||latest?.state!=='sending')return;
  let active=true;
  const poll=setInterval(()=>void publicationCall<Publication>(`/${draft.id}`,undefined,'GET').then(d=>{if(active){setDraft(d);setContent(d.content);}}).catch(()=>{}),2500);
  return()=>{active=false;clearInterval(poll);};
 },[draft?.id,latest?.state]);
 return <section className="publish-page publication-page" aria-label="已接受成片发布">
 <div className="publish-editor">
  <h1 className="page-title"><IconPublish size={21}/>成片发布</h1>
  <p className="page-subtitle">从已接受的具体版本准备投稿，草稿、账号与平台结果保存在同一条记录中。</p>
  <label className="field-label" htmlFor="publication-draft">发布记录</label>
  <div className="publication-picker"><select id="publication-draft" className="field" disabled={busy} value={draft?.id||''} onChange={e=>{const d=drafts.find(d=>d.id===e.target.value);if(d)select(d);}}>
   <option value="" disabled>选择发布草稿或记录</option>{drafts.map(d=><option key={d.id} value={d.id}>{d.content.title} · 版本{d.output_revision} · {publicationStatus(d)}</option>)}
  </select><button className="btn btn-sm" disabled={busy} aria-label="刷新原记录" onClick={()=>void run(async()=>{await refresh();if(draft)select(await publicationCall<Publication>(`/${draft.id}`,undefined,'GET'));})}><IconRefresh size={15}/></button></div>
  {error&&<p className="pv-pubstate fail" role="alert">{error}</p>}
  {!draft&&<div className="empty-state"><h3>选择一条已接受成片</h3><p>在内容库或原对话点击“准备发布”，即可打开对应版本的草稿。</p></div>}
  {draft&&content&&<>
   <button className="btn btn-sm" onClick={()=>openPublishSource(draft.work_id,draft.output_id)}>在发布中心选择平台</button>
   <div className="publication-status" role="status"><span className={`badge ${latest?.state==='verified'?'badge-ok':'badge-warn'}`}>{publicationStatus(draft)}</span><p>{publicationGuidance(draft)}</p></div>
   {draft.last_error?.message&&!latest&&<p className="pv-pubstate fail" role="alert">{draft.last_error.message}</p>}
   <fieldset className="publication-fields" disabled={busy||!!confirming}>
    <label className="field-label" htmlFor="publication-title">标题</label><input id="publication-title" className="field" readOnly={!editable} value={content.title} onChange={e=>update({title:e.target.value})}/>
    <label className="field-label" htmlFor="publication-body">简介</label><textarea id="publication-body" className="field publication-body" readOnly={!editable} value={content.body} onChange={e=>update({body:e.target.value})}/>
    <label className="field-label" htmlFor="publication-tags">标签（逗号分隔）</label><input id="publication-tags" className="field" readOnly={!editable} value={content.tags.join(',')} onChange={e=>update({tags:e.target.value.split(/[,，]/)})}/>
    {platform==='bilibili'&&<div className="publication-options"><BilibiliPartition value={content.tid} onChange={tid=>update({tid})} catalog={partitions.catalog} refresh={partitions.refresh} disabled={!editable||busy||!!confirming}/>
     <label className="field-label">稿件类型<select className="field" disabled={!editable} value={content.copyright} onChange={e=>update({copyright:Number(e.target.value)})}><option value={1}>自制</option><option value={2}>转载</option></select></label></div>}
    {content.copyright===2&&<label className="field-label">转载来源<input className="field" readOnly={!editable} value={content.source} onChange={e=>update({source:e.target.value})}/></label>}
    <PublicationCover key={`${draft.id}:${draft.revision}`} draft={draft} cover={content.cover} disabled={busy||!!confirming} onChange={cover=>update({cover})} run={run}/>
    <div className="publication-account"><div><span className="field-label">目标账号</span><strong>{content.account?content.account.name:'尚未读取'}</strong>{content.account&&platform==='bilibili'&&<small>UID {content.account.uid}</small>}</div>{editable&&<button className="btn btn-sm" onClick={()=>void run(async()=>update({account:await publicationCall<PublicationContent['account']>(`/account?platform=${platform}`)}))}>读取实际登录账号</button>}</div>
    {editable&&<div className="publish-actions"><button className="btn" onClick={()=>void run(async()=>select(await publicationCall<Publication>(`/${draft.id}`,{revision:draft.revision,content},'PUT')))}>保存草稿</button>
     <button className="btn btn-primary" disabled={dirty||!content.account||!content.tags.some(t=>t.trim())} onClick={()=>setConfirming('submit')}>查看最终确认并投稿</button>
     <button className="btn btn-ghost" onClick={()=>void run(async()=>select(await publicationCall<Publication>(`/${draft.id}/cancel`,{revision:draft.revision})))}>取消草稿</button></div>}
   </fieldset>
   {dirty&&<p className="publish-saved-note">内容已修改，请先保存，再查看最终确认。</p>}
   {busy&&<p className="pv-pubstate publishing" role="status">正在处理，请等待当前操作返回；不会重复提交。</p>}
   {platform==='bilibili'&&latest&&latest.state!=='failed_before_submit'&&<div className="publish-actions"><button className="btn" disabled={busy} onClick={()=>void run(async()=>select(await publicationCall<Publication>(`/${draft.id}/reconcile`)))}>仅核实原投稿结果</button><a className="btn btn-ghost" href="https://member.bilibili.com/platform/upload-manager/article" target="_blank" rel="noreferrer">B站稿件管理</a>{latest.state==='unknown'&&!latest.receipt.execution?.remote_id&&<button className="btn btn-ghost" disabled={busy} onClick={()=>setConfirming('resolve')}>已核实未投稿，重新准备</button>}</div>}
  </>}
 </div>
 <aside className="publish-previews" aria-label="发布预览与回执">
 {draft&&content?<>
  <article className="card pv-card"><header className="pv-head"><span className="pv-plat">{label} · 成片版本 {draft.output_revision}</span><span className="pv-count">已接受版本</span></header><video controls preload="metadata" poster={content.cover?publicationCoverURL(draft.id,content.cover.digest):undefined} src={artifactURL(draft.output_id)} className="publication-video"/><div className="pv-body"><h2 className="pv-title">{content.title}</h2><p className="pv-text">{content.body||'简介尚未填写'}</p></div><footer className="pv-foot"><span className="pv-hint">{content.tags.join(' · ')}</span></footer></article>
  <details className="card publication-details"><summary>素材署名（随简介提交）</summary><p className="pv-text">{content.credits||'无附加署名'}</p></details>
  {draft.attempts.map(a=><article key={a.id} className="card publication-details"><h3>投稿记录</h3><p>{publicationStatus({...draft,attempts:[a]})}</p>{a.receipt.reason&&<p className="page-subtitle">{a.receipt.reason}</p>}
   {a.receipt.url&&<a className="btn btn-sm" href={a.receipt.url} target="_blank" rel="noreferrer">查看平台稿件</a>}
   <details><summary>执行回执</summary>{a.receipt.execution?<p className="page-subtitle">{publicationExecutionText(a.receipt.execution)}工具{a.receipt.execution.timed_out?'执行超时':`已结束，退出码 ${a.receipt.execution.returncode}`}。{a.receipt.execution.response_codes?.length?`平台回执码：${a.receipt.execution.response_codes.join('、')}。`:''}退出码不代表投稿成功，最终以平台核实为准。</p>:<p className="page-subtitle">这次历史执行没有保存上传工具退出回执，无法确定停在上传还是投稿步骤；不会补造记录或重发。</p>}</details>
  </article>)}
 </>:<p className="page-subtitle">选定草稿后，在这里预览对应成片、发布内容与平台回执。</p>}
 </aside>
 {confirming==='submit'&&draft&&<div className="overlay" onClick={e=>{if(e.target===e.currentTarget)setConfirming(null);}}><div className="modal publication-confirm" role="dialog" aria-modal="true" aria-labelledby="publication-confirm-title">
  <h2 id="publication-confirm-title">确认向{label}投稿</h2><p className="page-subtitle">账号：{draft.content.account?.name} · 成片版本 {draft.output_revision}</p><h3>{draft.content.title}</h3><p className="pv-text">{draft.content.body}</p><p className="page-subtitle">标签：{draft.content.tags.join('、')}{platform==='bilibili'&&<> · 分区 {partitionLabel(partitions.catalog,draft.content.tid)}</>} · {draft.content.copyright===1?'自制':'转载'}</p><details><summary>随稿素材署名</summary><p className="pv-text">{draft.content.credits||'无附加署名'}</p></details><p className="page-subtitle">确认后会真实上传和投稿；平台审核状态以返回记录为准。</p>
  {draft.content.cover?<img className="publication-cover-image" src={publicationCoverURL(draft.id,draft.content.cover.digest)} alt="本次投稿确认封面"/>:<p className="page-subtitle">封面：使用平台默认处理。</p>}
  <div className="publish-actions"><button className="btn" autoFocus onClick={()=>setConfirming(null)}>返回修改</button><button className="btn btn-primary" disabled={busy} onClick={()=>void submit()}>确认投稿</button></div>
 </div></div>}
 {confirming==='resolve'&&draft&&<div className="overlay"><div className="modal publication-confirm" role="dialog" aria-modal="true" aria-labelledby="resolve-title">
  <h2 id="resolve-title">确认本片未投稿</h2><p className="page-subtitle">账号：{draft.content.account?.name} · 成片版本 {draft.output_revision}</p><h3>{draft.content.title}</h3>
  <p className="pv-text">确认已在B站稿件管理核对全部稿件、进行中、未通过和草稿，本片均不存在。系统还会核对原账号与发前稿件列表；列表变化或不完整时保留待核实状态。</p>
  <p className="page-subtitle">仅恢复原发布草稿并保留历史尝试，不会立即上传。仍需查看最终内容后确认投稿。</p>
  <div className="publish-actions"><button className="btn" autoFocus onClick={()=>setConfirming(null)}>返回核实</button><button className="btn btn-primary" disabled={busy} onClick={()=>void resolveAbsent()}>确认未投稿，恢复原草稿</button></div>
 </div></div>}
 </section>;
}
