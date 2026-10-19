import { useEffect, useState, useCallback, useRef } from 'react';
import { actionId, catalogCommand, enterVideo, videoRequest, applyProposal, type ConversationView, type Proposal, type VideoEntry } from '../lib/conversationApi';
import { productionRequest, workLabels, type Work, type Channel, type Director } from '../lib/productionApi';
import WorkCards from './WorkCards';
import { CONFIGURATION_PROMPTS, CONVERSATION_WORKFLOWS } from '../lib/conversationWorkflows';
import { directorEntrySelection, selectableDirectorVersions } from '../lib/directorLifecycle';

const labels:Record<string,string>={draft:'创建作品草稿',plan:'整理完整方案',revision:'修改指定成片',channel_create:'保存新频道',channel_defaults:'保存频道修改',director_formation:'分析参考并形成导演',profile:'保存长期画像偏好',director_revision:'另存导演风格版本'};
const styleLabels:Record<string,string>={visual_style:'画面风格',storytelling:'叙事方式',pacing:'节奏',sound:'声音',invariants:'保持不变',freedom:'创作自由',constraints:'边界',evidence_notes:'参考说明'};
function StyleSummary({style}:{style:Record<string,unknown>}) {
  return <dl className="creation-existing">{Object.entries(style).filter(([k])=>k!=='schema_version').map(([k,value])=><div key={k}><dt>{styleLabels[k]||k}</dt><dd>{Array.isArray(value)?value.join('\n'):typeof value==='string'?value:JSON.stringify(value)}</dd></div>)}</dl>;
}
function ProposalCard({proposal:p,onApply,busy,inputs=[],error}:{error?:string;inputs?:Work['inputs'];proposal:Proposal;onApply:(p:Proposal,dismiss?:boolean)=>void;busy:boolean}) {
  return <article className="work-card"><h3>{labels[p.kind]||p.kind} · {({proposed:'待确认',applied:'已保存',stale:'已失效',dismissed:'已放弃'} as Record<string,string>)[p.state]||p.state}</h3>
    <dl>{Object.entries(p.body.values).filter(([k])=>!['before_hash','base_revision'].includes(k)).map(([key,value])=><div key={key}><dt>{({name:'名称',title:'名称',input_text:'本期内容',request:'规划要求',feedback:'修改意见',creative_basis:'频道定位、主题与受众',settings:'默认设置',file:'目标画像文件',before_hash:'原版本',after:'保存后的内容',entries:'建议保存的条目',analysis_scope:'分析范围（visual仅画面与叙事，原音轨未分析；full含音轨）',reference_input_ids:'参考素材',protected:'保护项',interval:'修改区间',style:'新风格'} as Record<string,string>)[key]||key}</dt><dd style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{key==='reference_input_ids'&&Array.isArray(value)?value.map(id=>inputs.find(i=>i.id===id)?.original_name||'已登记参考').join('、'):key==='creative_basis'&&value&&typeof value==='object'?Object.entries(value).map(([k,v])=>`${({position:'定位',themes:'主题',audience:'受众'} as Record<string,string>)[k]||k}：${typeof v==='string'?v:JSON.stringify(v)}`).join('\n'):typeof value==='string'?value:JSON.stringify(value,null,2)}</dd></div>)}</dl>
    <p>来源：{p.body.source_refs.length}条本片用户消息。{p.body.target.profile_ref?`画像：${p.body.target.profile_name||'已选择'}`:'未选择画像'}{p.body.target.channel_id?` · 频道：${(p.body.target.channel as {name?:string})?.name||'已选择'}`:''}</p>
    {p.state==='proposed'&&<><button disabled={busy} onClick={()=>onApply(p)}>{labels[p.kind]}{p.kind==='director_formation'?'（可能需要服务授权）':''}</button><button disabled={busy} onClick={()=>onApply(p,true)}>不保存／放弃</button><p>可在对话中继续修改；新提案会使这张旧卡失效。</p></>}
    {error&&<p role="alert">{error}</p>}
    {p.receipt&&<details><summary>实际保存回执</summary><pre>{JSON.stringify(p.receipt,null,2)}</pre></details>}
  </article>;
}
export default function VideoConversation({sessionId,segmentId,persona,onBound,onDraft,onBindingPending,onRestore}:{sessionId:string;segmentId?:string;persona?:string;onRestore:(messages:{role:'user'|'assistant';content:string}[])=>void;onBound:(id:string)=>void;onDraft:(text:string)=>void;onBindingPending:(pending:boolean)=>void}) {
  const [referenceURL,setReferenceURL]=useState('');
  const [view,setView]=useState<ConversationView|null>(null);const [error,setError]=useState('');const [readError,setReadError]=useState('');const [busy,setBusy]=useState(false);const [proposalError,setProposalError]=useState<{id:string;message:string}|null>(null);
  const profile=persona||'';const [channel,setChannel]=useState('');const [director,setDirector]=useState('');
  const [operation,setOperation]=useState<'create'|'edit'>('create');
  const [work,setWork]=useState<Work|null>(null);
  const [channels,setChannels]=useState<Channel[]>([]);const [directors,setDirectors]=useState<Director[]>([]);
  const sequence=useRef(0);
  const restoredSegment=useRef('');
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
  const enter=async(entry:VideoEntry)=>{setBusy(true);setError('');try{const result=await enterVideo(sessionId,entry);onBound(result.segment_id);await load();return true;}catch(e){setError((e as Error).message);return false;}finally{setBusy(false);}};
  const selectedDirectorId=String((work?.settings as Record<string,unknown>|undefined)?.director_revision || (view?.context.settings as Record<string,unknown>|undefined)?.director_revision || '');
  const selectedDirector=directors.flatMap(d=>d.versions.map(v=>({name:d.name,version:v.revision,id:v.id,trial:!v.accepted_at}))).find(v=>v.id===selectedDirectorId);
  const directorChoices=selectableDirectorVersions(directors,true);
  const startNewWork=()=>{
    try { void enter({profile_ref:profile||undefined,channel_id:channel||undefined,...directorEntrySelection(directors,director),kind:'new_work'}); }
    catch(e) { setError((e as Error).message); }
  };
  const pending=view?.turns.some(t=>['reserved','active','dispatching','unknown'].includes(t.state));
  const workflow=CONVERSATION_WORKFLOWS.find(w=>w.kind===view?.context.kind);
  const channelFlow=workflow?.kind==='channel_create';const directorFlow=workflow?.kind==='director_formation';
  const managing=channelFlow||directorFlow;
  const boundChannel=channels.find(c=>c.id===view?.context.channel_id);
  const boundDirector=directors.flatMap(d=>d.versions).find(v=>v.id===selectedDirectorId);
  const boundOperation=(channelFlow&&view?.context.channel_id)||(directorFlow&&view?.context.director_source==='explicit')?'edit':'create';
  const targetPending=managing&&(operation!==boundOperation||(operation==='edit'&&(channelFlow?channel!==view?.context.channel_id:director!==selectedDirectorId)));
  useEffect(()=>{onBindingPending(busy||targetPending);},[busy,targetPending,onBindingPending]);
  useEffect(()=>()=>onBindingPending(false),[onBindingPending]);
  useEffect(()=>{
    if(!view||restoredSegment.current===view.segment_id)return;
    restoredSegment.current=view.segment_id;
    setChannel(view.context.channel_id||'');
    const settings=view.context.settings as Record<string,unknown>|undefined;
    setDirector(String(settings?.director_revision||''));
    setOperation((view.context.kind==='channel_create'&&view.context.channel_id)||(view.context.kind==='director_formation'&&view.context.director_source==='explicit')?'edit':'create');
  },[view]);
  const startManagement=async()=>{
    try {
      if(operation==='edit'&&!(channelFlow?channel:director))throw new Error(`请先选择要修改的${channelFlow?'频道':'导演版本'}`);
      const entered=await enter({kind:workflow!.kind,profile_ref:profile||undefined,
        ...(channelFlow&&operation==='edit'?{channel_id:channel}:{}),
        ...(directorFlow&&operation==='edit'?directorEntrySelection(directors,director):{})});
      if(!entered)return;
      onDraft(CONFIGURATION_PROMPTS[channelFlow?'channel_create':'director_formation'][operation]);
    } catch(e) { setError((e as Error).message); }
  };
  const apply=async(p:Proposal,dismiss=false)=>{setBusy(true);setProposalError(null);try{await applyProposal(sessionId,p,dismiss);await load();}catch(e){setProposalError({id:p.id,message:(e as Error).message});}finally{setBusy(false);}};
  return <section className="video-conversation" aria-label={channelFlow?'频道设置对话':directorFlow?'导演设置对话':'视频创作对话'}>
    {managing?<details className="creation-context" open><summary>{channelFlow?'频道':'导演'} · 创建与修改</summary>
      <p className="creation-profile">当前画像：{profile||'通用模式'} · 沿用外部选择</p>
      <div className="creation-actions" role="group" aria-label="设置操作"><button className={`btn btn-sm ${operation==='create'?'btn-primary':'btn-ghost'}`} disabled={busy||!!pending} onClick={()=>setOperation('create')}>新建{channelFlow?'频道':'导演'}</button><button className={`btn btn-sm ${operation==='edit'?'btn-primary':'btn-ghost'}`} disabled={busy||!!pending} onClick={()=>setOperation('edit')}>修改已有{channelFlow?'频道':'导演'}</button></div>
      {operation==='edit'&&(channelFlow?<label>要修改的频道<select value={channel} onChange={e=>setChannel(e.target.value)}><option value="">请选择频道</option>{channels.filter(c=>!c.archived&&c.profile_name===profile).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>:<label>要修改的导演版本<select value={director} onChange={e=>setDirector(e.target.value)}><option value="">请选择导演版本</option>{directorChoices.map(({director:d,version:v})=><option key={v.id} value={v.id}>{d.name} · 版本{v.revision}{v.accepted_at?'':'（待试片）'}</option>)}</select></label>)}
      <p className="creation-help">{channelFlow?'讨论定位、主题、受众及频道默认；确认后保存，不开始制作视频。':'先讨论参考与风格，再确认分析和版本；试片制作及接受是独立步骤。修改风格保留旧版本。'}</p>
      {channelFlow&&boundChannel&&<details className="creation-existing"><summary>当前频道配置 · {boundChannel.name}</summary><dl>{Object.entries(boundChannel.creative_basis||{}).map(([k,value])=><div key={k}><dt>{({position:'定位',themes:'主题',audience:'受众'} as Record<string,string>)[k]||k}</dt><dd>{value}</dd></div>)}</dl><p className="creation-help">未要求修改的声音、字幕和导演默认配置会保留。</p></details>}
      {directorFlow&&boundDirector&&<details className="creation-existing"><summary>当前导演风格 · 版本{boundDirector.revision}</summary><StyleSummary style={boundDirector.style}/><p className="creation-help">保留 {boundDirector.evidence.length} 条参考依据；修改后另存新版本，再确认风格。</p></details>}
      <button className="btn btn-primary" disabled={busy||!!pending} onClick={()=>void startManagement()}>开始{operation==='create'?'创建':'修改'}{channelFlow?'频道':'导演'}的对话</button>
    </details>:<details className="creation-context" open={!segmentId}><summary>{segmentId?'本期创作配置':'开始视频创作'}</summary><p className="creation-help">选用已有频道和导演，然后聊聊这次的想法。</p>
      <p className="creation-profile">当前画像：{profile||'通用模式'} · 沿用本对话的画像</p>
      <label>频道<select value={channel} onChange={e=>setChannel(e.target.value)}><option value="">不归属频道</option>{channels.filter(c=>!c.archived&&c.profile_name===profile).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label>明确选择导演<select value={director} onChange={e=>setDirector(e.target.value)}><option value="">沿用频道默认／根据本期内容创作</option>{directorChoices.map(({director:d,version:v})=><option key={v.id} value={v.id}>{d.name} · 版本{v.revision}{v.accepted_at?'':'（试片，尚未接受）'}</option>)}</select></label>
      {directorChoices.some(v=>v.version.id===director&&!v.version.accepted_at)&&<p role="status">本期首版将兼作此导演版本的试片；选择不会标记已接受，也不会设为频道默认导演。</p>}
      <button className="btn btn-primary" disabled={busy||!!pending} onClick={startNewWork}>{segmentId?'使用这些配置':'进入视频创作对话'}</button>
      {view?.work_id&&<p>现有作品的方案保持原依据；新作品会使用独立对话运行段。</p>}
    </details>}
    {(error||readError)&&<p role="alert">{error||readError}</p>}
    {workflow&&!managing&&!view?.work_id&&<p role="status">当前管线：{workflow.label} · {workflow.desc}</p>}
    {view&&<><p className="creation-help">{managing?`当前目标：${channelFlow?(boundChannel?.name||'新建频道'):(selectedDirector?`${selectedDirector.name} · 版本${selectedDirector.version}`:'新建导演')}`:`本次：${String(view.context.profile_name||'通用画像')} · ${view.context.channel?.name||'独立创作'} · ${selectedDirector?`导演：${selectedDirector.name} · 版本${selectedDirector.version}${selectedDirector.trial?'（试片，尚未接受）':''}`:'采用入口选定依据'}`}{pending?' · 本轮正在运行／待核实':''}</p><button disabled={!!pending} onClick={()=>onRestore(view.messages)}>恢复本段可见讨论</button>
      {directorFlow&&directors.filter(d=>(d.versions.some(v=>v.id===selectedDirectorId)&&d.versions[0]?.id!==selectedDirectorId)||work?.tasks.some(t=>t.kind==='analyze_director'&&JSON.parse(t.payload_json||'{}').director_id===d.id)).map(d=><article className="work-card" key={d.id}><h3>{d.name} · 参考形成的导演</h3>{d.versions.filter(v=>v===d.versions[0]&&v.id!==selectedDirectorId).map(v=><div key={v.id}><h4>风格版本{v.revision}</h4><details><summary>查看风格与参考说明</summary><StyleSummary style={v.style}/><p className="creation-help">基于 {v.evidence.length} 条已登记参考依据。</p></details>
        {!v.style_confirmed?<button disabled={busy||!!pending} onClick={async()=>{setBusy(true);try{await catalogCommand(`directors/${d.id}`,d.revision,{revision_id:v.id,style_confirmed:true},'PATCH');setDirectors(await productionRequest<Director[]>('directors'));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>确认此风格，保留为待试片草稿</button>:work?.plans.some(p=>p.confirmed_at)?<p>{selectedDirectorId===v.id?'本片已采用此导演版本。':'本片已有确认方案；更换导演请围绕具体成片讨论修订。'}</p>:<button className="btn btn-primary" disabled={busy||!!pending} onClick={async()=>{const entered=await enter({kind:'new_work',profile_ref:profile||undefined,channel_id:view.context.channel_id||undefined,...directorEntrySelection(directors,v.id)});if(entered)onDraft('使用刚才选定的导演风格创作一条新视频，作为此版本的试片。请先和我讨论本期想法；完整方案及制作等我确认。');}}>用此版本进入试片创作</button>}
      </div>)}</article>)}
      {directorFlow&&work&&<details><summary>导入公开参考视频直链</summary><p>只用于参考，不赋予重剪或原声复用权；网页链接请先取得实际视频文件。</p><input aria-label="参考视频直链" type="url" value={referenceURL} onChange={e=>setReferenceURL(e.target.value)} placeholder="https://…/reference.mp4"/><button disabled={busy||!!pending||!referenceURL.trim()} onClick={async()=>{setBusy(true);try{await videoRequest(`${sessionId}/reference-import`,'POST',{command_id:actionId(sessionId+':reference',{url:referenceURL,work:work.id,revision:work.revision}),segment_id:view.segment_id,expected_revision:work.revision,url:referenceURL});setReferenceURL('');await load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>确认导入为风格参考</button></details>}
      {view.proposals.filter(p=>channelFlow?['channel_create','channel_defaults'].includes(p.kind):directorFlow?['draft','director_formation','director_revision'].includes(p.kind):!['channel_create','channel_defaults','director_formation','director_revision','profile'].includes(p.kind)).map(p=><ProposalCard key={p.id} inputs={work?.inputs} proposal={p} error={proposalError?.id===p.id?proposalError.message:undefined} busy={busy||!!pending} onApply={(p,d)=>void apply(p,d)}/>)}
      {!managing&&view.proposals.some(p=>p.state==='proposed'&&['channel_create','channel_defaults','director_formation','director_revision','profile'].includes(p.kind))&&<p role="status" className="creation-help">本期对话中有尚未保存的长期配置提案，原记录已保留。频道或导演设置请从笔入口进入对应管线；画像在外部画像页处理。</p>}
      {view.work_id&&!channelFlow&&<details open={!!work&&['awaiting_confirmation','needs_decision','reviewable','preview_needs_fix'].includes(work.state)}><summary>{directorFlow?'参考素材与分析进度':`作品详情 · ${work?workLabels[work.state]||work.state:'正在读取'} · 方案、进度与审片`}</summary><WorkCards referenceOnly={directorFlow} key={view.work_id} workId={view.work_id} sessionId={sessionId} onChanged={()=>{void load();void Promise.all([productionRequest<Director[]>('directors').then(setDirectors),productionRequest<Channel[]>('channels').then(setChannels)]);}} onContinue={entry=>void enter(entry)}/></details>}
    </>}
  </section>;
}
