import { useEffect, useState, useCallback, useRef } from 'react';
import { actionId, catalogCommand, workCommand, enterVideo, videoRequest, applyProposal, type ConversationView, type Proposal, type VideoEntry } from '../lib/conversationApi';
import { productionRequest, workLabels, type Work, type Channel, type Director } from '../lib/productionApi';
import type { PersonaItem } from '../lib/api';
import WorkCards from './WorkCards';
import { CONVERSATION_WORKFLOWS } from '../lib/conversationWorkflows';
import { directorEntrySelection, selectableDirectorVersions } from '../lib/directorLifecycle';

const labels:Record<string,string>={draft:'创建作品草稿',plan:'整理完整方案',revision:'修改指定成片',channel_create:'保存新频道',channel_defaults:'保存频道默认',director_formation:'分析参考并形成导演',profile:'保存长期画像偏好',director_revision:'另存导演风格版本'};
function ProposalCard({proposal:p,onApply,busy,inputs=[],error}:{error?:string;inputs?:Work['inputs'];proposal:Proposal;onApply:(p:Proposal,dismiss?:boolean)=>void;busy:boolean}) {
  return <article className="work-card"><h3>{labels[p.kind]||p.kind} · {({proposed:'待确认',applied:'已保存',stale:'已失效',dismissed:'已放弃'} as Record<string,string>)[p.state]||p.state}</h3>
    <dl>{Object.entries(p.body.values).filter(([k])=>!['before_hash','base_revision'].includes(k)).map(([key,value])=><div key={key}><dt>{({name:'名称',title:'名称',input_text:'本期内容',request:'规划要求',feedback:'修改意见',creative_basis:'频道定位、主题与受众',settings:'默认设置',file:'目标画像文件',before_hash:'原版本',after:'保存后的内容',entries:'建议保存的条目',analysis_scope:'分析范围（visual仅画面与叙事，原音轨未分析；full含音轨）',reference_input_ids:'参考素材',protected:'保护项',interval:'修改区间',style:'新风格'} as Record<string,string>)[key]||key}</dt><dd style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{key==='reference_input_ids'&&Array.isArray(value)?value.map(id=>inputs.find(i=>i.id===id)?.original_name||'已登记参考').join('、'):key==='creative_basis'&&value&&typeof value==='object'?Object.entries(value).map(([k,v])=>`${({position:'定位',themes:'主题',audience:'受众'} as Record<string,string>)[k]||k}：${typeof v==='string'?v:JSON.stringify(v)}`).join('\n'):typeof value==='string'?value:JSON.stringify(value,null,2)}</dd></div>)}</dl>
    <p>来源：{p.body.source_refs.length}条本片用户消息。{p.body.target.profile_ref?`画像：${p.body.target.profile_name||'已选择'}`:'未选择画像'}{p.body.target.channel_id?` · 频道：${(p.body.target.channel as {name?:string})?.name||'已选择'}`:''}</p>
    {p.state==='proposed'&&<><button disabled={busy} onClick={()=>onApply(p)}>{labels[p.kind]}{p.kind==='director_formation'?'（可能需要服务授权）':''}</button><button disabled={busy} onClick={()=>onApply(p,true)}>不保存／放弃</button><p>可在对话中继续修改；新提案会使这张旧卡失效。</p></>}
    {error&&<p role="alert">{error}</p>}
    {p.receipt&&<details><summary>实际保存回执</summary><pre>{JSON.stringify(p.receipt,null,2)}</pre></details>}
  </article>;
}
export default function VideoConversation({sessionId,segmentId,persona,personas,onBound,onRequest,onRestore}:{sessionId:string;segmentId?:string;persona?:string;personas:PersonaItem[];onRestore:(messages:{role:'user'|'assistant';content:string}[])=>void;onBound:(id:string)=>void;onRequest:(text:string)=>void}) {
  const [referenceURL,setReferenceURL]=useState('');
  const [view,setView]=useState<ConversationView|null>(null);const [error,setError]=useState('');const [readError,setReadError]=useState('');const [busy,setBusy]=useState(false);const [proposalError,setProposalError]=useState<{id:string;message:string}|null>(null);
  const [profile,setProfile]=useState(persona||'');const [channel,setChannel]=useState('');const [director,setDirector]=useState('');
  const [work,setWork]=useState<Work|null>(null);
  const [channels,setChannels]=useState<Channel[]>([]);const [directors,setDirectors]=useState<Director[]>([]);
  const sequence=useRef(0);
  const load=useCallback(async(isCurrent:()=>boolean=()=>true)=>{
    const request=++sequence.current;
    try {
      const next=await videoRequest<ConversationView>(encodeURIComponent(sessionId));
      const snapshot=next.work_id?await productionRequest<Work>(`works/${next.work_id}`):null;
      if(request!==sequence.current||!isCurrent())return;
      setView(next);setWork(snapshot);setReadError('');
      if(next.segment_id!==segmentId)onBound(next.segment_id);
    } catch(e) {
      if(request===sequence.current&&isCurrent()&&segmentId)setReadError((e as Error).message);
    }
  },[sessionId,segmentId,onBound]);
  useEffect(()=>{
    let active=true;
    const refresh=()=>void load(()=>active);
    refresh();const poll=setInterval(refresh,2500);
    return()=>{active=false;clearInterval(poll);};
  },[load]);
  const appliedCount=view?.proposals.filter(p=>p.state==='applied').length;
  useEffect(()=>{Promise.all([productionRequest<Channel[]>('channels').then(setChannels),productionRequest<Director[]>('directors').then(setDirectors)]).catch(()=>{});},[view?.work_id,work?.revision,appliedCount]);
  const enter=async(entry:VideoEntry)=>{setBusy(true);setError('');try{const result=await enterVideo(sessionId,entry);onBound(result.segment_id);await load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const selectedDirectorId=String((work?.settings as Record<string,unknown>|undefined)?.director_revision || (view?.context.settings as Record<string,unknown>|undefined)?.director_revision || '');
  const selectedDirector=directors.flatMap(d=>d.versions.map(v=>({name:d.name,version:v.revision,id:v.id,trial:!v.accepted_at}))).find(v=>v.id===selectedDirectorId);
  const directorChoices=selectableDirectorVersions(directors,true);
  const startNewWork=()=>{
    try { void enter({profile_ref:profile||undefined,channel_id:channel||undefined,...directorEntrySelection(directors,director),kind:'new_work'}); }
    catch(e) { setError((e as Error).message); }
  };
  const pending=view?.turns.some(t=>['reserved','active','dispatching','unknown'].includes(t.state));
  const workflow=CONVERSATION_WORKFLOWS.find(w=>w.kind===view?.context.kind);
  const apply=async(p:Proposal,dismiss=false)=>{setBusy(true);setProposalError(null);try{await applyProposal(sessionId,p,dismiss);await load();}catch(e){setProposalError({id:p.id,message:(e as Error).message});}finally{setBusy(false);}};
  return <section className="video-conversation" aria-label="视频创作对话">
    <details open={!segmentId}><summary>{segmentId?'视频创作 · 查看／切换创作依据':'进入对话式视频创作'}</summary><p>选择已配置的画像、频道与导演，不重新整理六维画像；制作和长期保存由明确卡片确认。</p>
      <label>六维画像<select value={profile} onChange={e=>{setProfile(e.target.value);setChannel('');}}><option value="">不选画像也能创作</option>{personas.map(p=><option key={p.name}>{p.name}</option>)}</select></label>
      <label>频道<select value={channel} onChange={e=>{setChannel(e.target.value);const c=channels.find(c=>c.id===e.target.value);if(c)setProfile(c.profile_name);}}><option value="">不归属频道</option>{channels.filter(c=>!c.archived&&(!profile||c.profile_name===profile)).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label>明确选择导演<select value={director} onChange={e=>setDirector(e.target.value)}><option value="">沿用频道默认／根据本期内容创作</option>{directorChoices.map(({director:d,version:v})=><option key={v.id} value={v.id}>{d.name} · 版本{v.revision}{v.accepted_at?'':'（试片，尚未接受）'}</option>)}</select></label>
      {directorChoices.some(v=>v.version.id===director&&!v.version.accepted_at)&&<p role="status">本期首版将兼作此导演版本的试片；选择不会标记已接受，也不会设为频道默认导演。</p>}
      <button disabled={busy||!!pending} onClick={startNewWork}>{segmentId?'按这些依据讨论新作品':'进入视频创作对话'}</button>
      {view?.work_id&&<p>现有作品的方案保持原依据；新作品会使用独立对话运行段。</p>}
    </details>
    {(error||readError)&&<p role="alert">{error||readError}</p>}
    {workflow&&!view?.work_id&&<p role="status">当前管线：{workflow.label} · {workflow.desc}</p>}
    {view&&<><p>本次：{String(view.context.profile_name||'通用画像')} · {view.context.channel?.name||'独立创作'} · {selectedDirector?`导演：${selectedDirector.name} · 版本${selectedDirector.version}${selectedDirector.trial?'（试片，尚未接受）':''}`:'采用入口选定依据'}{pending?' · 本轮正在运行／待核实':''}</p><button disabled={!!pending} onClick={()=>onRestore(view.messages)}>恢复本段可见讨论</button>
      {!view.work_id&&<div><button disabled={busy||!!pending} onClick={()=>onRequest('我想创建一个频道，请先和我讨论名称、定位、主题和受众，整理未保存的频道提案。')}>讨论创建频道</button><button disabled={busy||!!pending} onClick={()=>onRequest('我想用参考视频形成一个导演，请先说明参考与风格要求；分析和制作都等我确认。')}>讨论创建导演</button></div>}
      {directors.filter(d=>work?.tasks.some(t=>t.kind==='analyze_director'&&JSON.parse(t.payload_json||'{}').director_id===d.id)).map(d=><article className="work-card" key={d.id}><h3>{d.name} · 参考形成的导演</h3>{d.versions.map(v=><div key={v.id}><h4>风格版本{v.revision}</h4><p>{String(v.style.visual_style||'')}</p><p>{String(v.style.storytelling||'')}</p><details><summary>完整风格与参考证据</summary><pre>{JSON.stringify({style:v.style,evidence:v.evidence},null,2)}</pre></details>
        {!v.style_confirmed?<button disabled={busy||!!pending} onClick={async()=>{setBusy(true);try{await catalogCommand(`directors/${d.id}`,d.revision,{revision_id:v.id,style_confirmed:true},'PATCH');setDirectors(await productionRequest<Director[]>('directors'));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>确认此风格，保留为待试片草稿</button>:work?.plans.some(p=>p.confirmed_at)?<p>{selectedDirectorId===v.id?'本片已采用此导演版本。':'本片已有确认方案；更换导演请围绕具体成片讨论修订。'}</p>:<button disabled={busy||!!pending} onClick={async()=>{if(!work)return;setBusy(true);try{await workCommand(work.id,work.revision,'basis',{settings:{director_revision:v.id,director_trial:!v.accepted_at}});await load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>让本期正式首版兼作此导演试片</button>}
      {v.accepted_at&&view.context.channel_id&&<button disabled={busy||!!pending||channels.some(c=>c.id===view.context.channel_id&&c.default_director_revision===v.id)} onClick={async()=>{const c=channels.find(c=>c.id===view.context.channel_id);if(!c)return;setBusy(true);try{await catalogCommand(`channels/${c.id}`,c.revision,{director_ids:Array.from(new Set([...c.director_ids,d.id])),default_director_revision:v.id},'PATCH');setChannels(await productionRequest<Channel[]>('channels'));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>{channels.some(c=>c.id===view.context.channel_id&&c.default_director_revision===v.id)?'已是本频道默认导演':'关联并设为本频道默认导演'}</button>}</div>)}</article>)}
      {work&&<details><summary>导入公开参考视频直链</summary><p>只用于参考，不赋予重剪或原声复用权；网页链接请先取得实际视频文件。</p><input aria-label="参考视频直链" type="url" value={referenceURL} onChange={e=>setReferenceURL(e.target.value)} placeholder="https://…/reference.mp4"/><button disabled={busy||!!pending||!referenceURL.trim()} onClick={async()=>{setBusy(true);try{await videoRequest(`${sessionId}/reference-import`,'POST',{command_id:actionId(sessionId+':reference',{url:referenceURL,work:work.id,revision:work.revision}),segment_id:view.segment_id,expected_revision:work.revision,url:referenceURL});setReferenceURL('');await load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>确认导入为风格参考</button></details>}
      {view.proposals.map(p=><ProposalCard key={p.id} inputs={work?.inputs} proposal={p} error={proposalError?.id===p.id?proposalError.message:undefined} busy={busy||!!pending} onApply={(p,d)=>void apply(p,d)}/>)}
      {view.work_id&&<details open={!!work&&['awaiting_confirmation','needs_decision','reviewable','preview_needs_fix'].includes(work.state)}><summary>作品详情 · {work?workLabels[work.state]||work.state:'正在读取'} · 方案、进度与审片</summary><WorkCards key={view.work_id} workId={view.work_id} sessionId={sessionId} onChanged={()=>{void load();void Promise.all([productionRequest<Director[]>('directors').then(setDirectors),productionRequest<Channel[]>('channels').then(setChannels)]);}} onContinue={entry=>void enter(entry)}/></details>}
    </>}
  </section>;
}
