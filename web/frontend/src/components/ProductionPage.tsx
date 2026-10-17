import { selectableDirectorVersions, trialOutputs } from '../lib/directorLifecycle';
import { useCallback, useEffect, useRef, useState } from 'react';
import { uploadFiles } from '../lib/api';
import type { PersonaItem } from '../lib/api';
import { artifactURL, newerSnapshot, productionCommand, productionRequest, productionURL, workLabels } from '../lib/productionApi';
import type { Channel, CreativePlan, Director, ServiceChoice, Work, WorkSummary } from '../lib/productionApi';
import ProductionSettings from './ProductionSettings';
import type { VoiceOption } from '../lib/productionSettings';
import type { VideoSettings } from '../lib/productionApi';
import './production.css';

const taskLabels: Record<string, string> = { plan: '创作方案', analyze_director: '拆解参考风格', supply: '寻找素材', select: '选择素材', edit: '编辑作品', render: '渲染视频', inspect: '检查画面与声音', quality:'检查画面与声音', voice_preview:'声音试听', review: '交付首版', revise: '理解修改范围' };
const stateLabels: Record<string, string> = { pending: '等待执行', running: '正在进行', waiting_external: '等待服务结果', retryable_failed: '等待恢复', needs_decision: '需要决定', failed: '未完成', succeeded: '已完成', cancelled: '已取消' };
const sessionKey = 'easel-production-upload-session';
function uploadSession() { let value = localStorage.getItem(sessionKey); if (!value) { value = crypto.randomUUID(); localStorage.setItem(sessionKey, value); } return value; }

export default function ProductionPage({ personas, selectedPersona }: { personas: PersonaItem[]; selectedPersona: string }) {
  const [works, setWorks] = useState<WorkSummary[]>([]); const [selected, setSelected] = useState('');
  const selectedRef = useRef(''); const [work, setWork] = useState<Work | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]); const [directors, setDirectors] = useState<Director[]>([]);
  const [services, setServices] = useState<ServiceChoice[]>([]); const [approved, setApproved] = useState<string[]>([]);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [connected, setConnected] = useState(false);
  const [title, setTitle] = useState(''); const [brief, setBrief] = useState(''); const [profile, setProfile] = useState(selectedPersona);
  const [channel, setChannel] = useState(''); const [director, setDirector] = useState(''); const [duration, setDuration] = useState(90);
  const [audio, setAudio] = useState('silent'); const [aspect, setAspect] = useState('9:16');
  const [imageLimit, setImageLimit] = useState(0); const [videoLimit, setVideoLimit] = useState(0); const [allowAI, setAllowAI] = useState(false);
  const [sourceStart,setSourceStart] = useState(''); const [sourceEnd,setSourceEnd] = useState('');
  const [usage, setUsage] = useState('reference'); const [originalAudio, setOriginalAudio] = useState(false);
  const [feedback, setFeedback] = useState(''); const [editing, setEditing] = useState<CreativePlan | null>(null);
  const [deletion, setDeletion] = useState<{preview_hash:string;expected_revision:number;output_id?:string;artifact_ids:string[];preserved_artifact_ids:string[];clears_acceptance:boolean;deferred_cleanup:boolean} | null>(null);
  const [compare, setCompare] = useState(''); const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [directorEdits, setDirectorEdits] = useState<Record<string,{visual_style:string;storytelling:string}>>({});
  const [catalogName, setCatalogName] = useState('');
  const [directorReferences,setDirectorReferences] = useState<string[]>([]);
  const [settingsHashes, setSettingsHashes] = useState<Record<string,string>>({});
  const [settingsDraft, setSettingsDraft] = useState<VideoSettings | null>(null);
  const [voices, setVoices] = useState<VoiceOption[]>([]); const [fonts, setFonts] = useState<{id:string;label:string}[]>([]);
  const [trial, setTrial] = useState(false); const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [stockQuery, setStockQuery] = useState('');
  const [stockSearching, setStockSearching] = useState(false);
  const [stockPreviews, setStockPreviews] = useState<{asset_id:string;preview_url:string;source_page:string;creator:string;creator_page:string}[]>([]);

  const loadList = useCallback(async (after?: string) => {
    const data = await productionRequest<{ items: WorkSummary[]; next_cursor: string | null }>(`works${after ? '?after=' + encodeURIComponent(after) : ''}`);
    setWorks(old => after ? [...old, ...data.items] : data.items); setNextCursor(data.next_cursor);
  }, []);
  const refresh = useCallback(async (id: string) => {
    const snapshot = await productionRequest<Work>(`works/${id}`);
    setWork(current => newerSnapshot(current, snapshot, selectedRef.current));
  }, []);
  const loadCatalog = useCallback(async () => {
    const [ch, dr] = await Promise.all([productionRequest<Channel[]>('channels'), productionRequest<Director[]>('directors')]);
    setChannels(ch); setDirectors(dr);
  }, []);
  useEffect(() => { Promise.all([loadList(), loadCatalog(), productionRequest<{ services: ServiceChoice[] }>('capabilities').then(data => setServices(data.services))]).catch(e => setError(String(e.message))); }, [loadList, loadCatalog]);
  useEffect(() => {
    selectedRef.current = selected; setSettingsDraft(null); setDeletion(null); setWork(null); setEditing(null); setConnected(false);
    if (!selected) return;
    let disposed = false; let stream: EventSource | undefined;
    const start = async () => {
      const snapshot = await productionRequest<Work>(`works/${selected}`);
      if (disposed) return;
      setWork(snapshot);
      const [configuration, voiceOptions, fontOptions] = await Promise.all([
        productionRequest<{settings:Partial<VideoSettings>;hashes:Record<string,string>}>(`works/${selected}/settings`),
        productionRequest<{voices:VoiceOption[]}>(`voice-options?work_id=${selected}`),
        productionRequest<{fonts:{id:string;label:string}[]}>('subtitle-fonts')]);
      if (disposed) return;
      setSettingsHashes(configuration.hashes);
      setSettingsDraft({duration_seconds:90,aspect_ratio:'9:16',audio_mode:'silent',...configuration.settings});
      setVoices(voiceOptions.voices);setFonts(fontOptions.fonts);
      stream = new EventSource(productionURL(`works/${selected}/events?after=${snapshot.cursor}`));
      stream.onopen = () => setConnected(true);
      stream.onerror = () => { setConnected(false); if (!disposed) refresh(selected).catch(e => setError(e.message)); };
      const update = () => { if (!disposed) refresh(selected).catch(e => setError(e.message)); };
      for (const event of ['snapshot','command_accepted','task_started','task_completed','task_succeeded','task_failed','task_waiting_external','task_retryable_failed','task_needs_decision','run_claimed','run_superseded','quality_repair_requested','render_cancel_observed','render_preserved','artifact_registered','artifact_created','render_progress','operation_reserved','operation_sending','operation_observed','operation_waiting','decision_required','revision_created','quality_result','quality_checked','quality_progress','revision_proposed','run_completed','run_cancelled','plan_created','director_analyzed','output_accepted']) stream.addEventListener(event, update);
    };
    start().catch(e => setError(e.message));
    return () => { disposed = true; stream?.close(); };
  }, [selected, refresh]);

  const perform = async (action: () => Promise<unknown>) => {
    setBusy(true); setError('');
    try { await action(); await loadList(); await loadCatalog(); if (selectedRef.current) await refresh(selectedRef.current); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const permissions = services.filter(s => approved.includes(`${s.provider}/${s.model}/${s.mode}`)).map(({ provider, model, mode }) => ({ provider, model, mode }));
  const latest = work?.plans[0];
  const outputs = work?.artifacts.filter(a => a.output_revision != null) ?? [];
  const active = work?.runs.find(r => r.id === work.active_run_id && ['pending','running','waiting_external','needs_decision','paused','failed'].includes(r.state));
  const command = (suffix: string, payload: Record<string, unknown>) => {
    if (!work) return Promise.reject(new Error('请先选择作品'));
    return productionCommand(`works/${work.id}/${suffix}`, payload, work.revision);
  };

  return <div className="production-page">
    <header><h1>视频创作</h1><p>从主题、素材或原片开始，让导演完成创作，再审阅和修改。</p></header>
    {error && <div role="alert" className="production-error">{error}<button onClick={() => { setError(''); loadList().catch(e => setError(e.message)); }}>重新读取</button></div>}
    <div className="production-layout">
      <aside className="production-panel"><h2>我的作品</h2><button onClick={() => setSelected('')}>新作品</button>
        {works.map(w => <button className={selected === w.id ? 'selected' : ''} key={w.id} onClick={() => setSelected(w.id)}><strong>{w.title}</strong><small>{workLabels[w.state] || w.state}{w.accepted_output_id ? ' · 已接受版本' : ''}</small></button>)}
        {nextCursor && <button onClick={() => loadList(nextCursor).catch(e => setError(e.message))}>加载更多</button>}
      </aside>
      <main className="production-panel">
        {!selected && <form onSubmit={e => { e.preventDefault(); perform(async () => {
          const result = await productionCommand<{ work_id: string }>('works',{ title, input_text: brief, profile_ref: profile || null, channel_id: channel || null, session_id: uploadSession(),
            settings: { duration_seconds: duration, aspect_ratio: aspect, audio_mode: audio, ...(director ? { director_revision: director, director_trial: trial } : {}) } });
          setSelected(result.work_id);
        }); }}>
          <h2>开始创作</h2><label>作品名称<input value={title} required maxLength={200} onChange={e => setTitle(e.target.value)} /></label>
          <label>主题、文案与明确要求<textarea value={brief} onChange={e => setBrief(e.target.value)} placeholder="想讲什么？有哪些必须保留的观点或经历？" rows={5} /></label>
          <div className="production-grid"><label>六维画像<select value={profile} onChange={e => { setProfile(e.target.value); setChannel(''); }}><option value="">不选画像</option>{personas.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}</select></label>
            <label>频道<select value={channel} onChange={e => { setChannel(e.target.value); const ch = channels.find(c => c.id === e.target.value); setDirector(ch?.default_director_revision || ''); }}><option value="">不归属频道</option>{channels.filter(c => !c.archived && c.profile_name === profile).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
            <label>导演<select value={director} onChange={e => setDirector(e.target.value)}><option value="">根据本次内容创作</option>{selectableDirectorVersions(directors,trial).map(({director:d,version:v}) => <option value={v.id} key={v.id}>{d.name} · 版本{v.revision}</option>)}</select></label>
            <label><input type="checkbox" checked={trial} onChange={e => { setTrial(e.target.checked); setDirector(''); }} />本片作为新导演版本试片</label><label>时长（秒）<input type="number" min={1} max={900} value={duration} onChange={e => setDuration(Number(e.target.value))} /></label>
            <label>画幅<select value={aspect} onChange={e => setAspect(e.target.value)}><option value="9:16">竖屏 9:16</option><option value="16:9">横屏 16:9</option></select></label>
            <label>声音<select value={audio} onChange={e => setAudio(e.target.value)}><option value="silent">静音</option><option value="music">纯音乐</option><option value="voice">纯旁白</option><option value="mixed">旁白与音乐</option></select></label></div>
          <button disabled={busy} type="submit">创建作品</button>
        </form>}
        {services.some(s => s.provider === 'unsplash' && s.available) && <details>
          <summary>Unsplash 参考图检索（仅预览，不进入制作）</summary>
          <p>只在点击检索时使用已配置的 Unsplash API；图片使用官方热链接，并保留摄影师与平台署名。当前未支持选中后下载追踪，不能将预览当作已获准的制作素材。</p>
          <form onSubmit={async e => { e.preventDefault(); if (!stockQuery.trim() || stockSearching) return;
            setStockSearching(true); setStockPreviews([]); setError('');
            try {
              const response = await productionRequest<{results:typeof stockPreviews}>('material-sources/unsplash/preview-search',
                {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:stockQuery.trim(),limit:8})});
              setStockPreviews(response.results);
            } catch(err) {setError(err instanceof Error ? err.message : 'Unsplash 预览检索失败');}
            finally {setStockSearching(false);}
          }}>
            <label>图片关键词<input value={stockQuery} maxLength={140} onChange={e => setStockQuery(e.target.value)} placeholder="例如 城市夜景" /></label>
            <button disabled={stockSearching || !stockQuery.trim()} type="submit">{stockSearching ? '检索中…' : '检索参考图'}</button>
          </form>
          {stockPreviews.map(item => <article className="production-stock-preview" key={item.asset_id}>
            <img src={item.preview_url} alt={'Unsplash 参考预览 · ' + item.creator} loading="lazy" />
            <p>摄影师：<a href={item.creator_page} target="_blank" rel="noopener noreferrer">{item.creator}</a> · <a href={item.source_page} target="_blank" rel="noopener noreferrer">Unsplash 原始来源</a> · 不可直接用于本片制作</p>
          </article>)}
        </details>}
        {selected && !work && <p>正在读取作品…</p>}
        {work && <>
          <h2>{work.title}</h2><p>{workLabels[work.state] || work.state} · {connected ? '进度已连接' : '连接恢复中，展示最后已知状态'}{work.accepted_output_id ? ' · 已保留接受版本' : ''}</p>
          <p>{work.input_text}</p>
          {settingsDraft && <details><summary>旁白与字幕设置 · {settingsDraft.voice?.voice_id || '未固定音色'} · 字号 {settingsDraft.subtitles?.size || 48}</summary><ProductionSettings key={work.id} settings={settingsDraft} voices={voices} fonts={fonts} disabled={busy || !!active}
            availableScopes={{channel:!!work.channel_id,profile:!!work.profile_ref}} onChange={setSettingsDraft}
            onSave={async(scope,settings) => {
              await command('settings',{scope,settings,expected_settings_hash:settingsHashes[scope]});
              const current = await productionRequest<{hashes:Record<string,string>}>(`works/${work.id}/settings`);
              setSettingsHashes(current.hashes);
              await refresh(work.id);await loadCatalog();
            }}
            onPreview={async(kind,settings,text,options) => {
              if (kind === 'voice') {
                await command('voice-previews',{voice:settings.voice,text,services:permissions,regenerate:options?.regenerate || false});await refresh(work.id);
                return {kind,message:'试听已进入制作任务；完成后可在下方音频成果中播放。'};
              }
              const frame=outputs[0] || work.artifacts.find(a => a.media_type.startsWith('image/') || a.media_type.startsWith('video/'));
              const input=work.inputs.find(i => i.kind === 'image' || i.kind === 'video');
              const result=await productionCommand<{artifact_id:string;reused:boolean}>(`works/${work.id}/subtitle-previews`,{settings:settings.subtitles,text,...(frame ? {frame_artifact_id:frame.id} : {frame_input_id:input?.id})},work.revision);
              await refresh(work.id);return {kind,url:artifactURL(result.artifact_id),reused:result.reused};
            }} /></details>}
          {work.artifacts.filter(a => a.media_type.startsWith('audio/')).map(a => <div key={a.id}><p>声音成果</p><audio controls src={artifactURL(a.id)} /></div>)}
          <details open={!latest}><summary>创作输入与素材</summary>
            {work.inputs.map(input => <p key={input.id}>{input.original_name || input.text_content.slice(0,80)} · {input.usage === 'must_use' ? '必须使用' : '仅供参考'}</p>)}
            <label>新增素材用途<select value={usage} onChange={e => setUsage(e.target.value)}><option value="reference">仅供参考</option><option value="must_use">必须使用</option></select></label>
            <label><input type="checkbox" checked={originalAudio} onChange={e => setOriginalAudio(e.target.checked)} />保留素材原声</label>
            {originalAudio && <div className="production-grid"><label>必须保留的原声起点（秒，可留空）<input type="number" min={0} step={0.1} value={sourceStart} onChange={e => setSourceStart(e.target.value)} /></label><label>原声终点（秒）<input type="number" min={0} step={0.1} value={sourceEnd} onChange={e => setSourceEnd(e.target.value)} /></label></div>}
            <label><input type="checkbox" checked={rightsConfirmed} onChange={e => setRightsConfirmed(e.target.checked)} />我拥有本次上传素材的使用权，允许用于本作品制作</label>
            <input type="file" multiple disabled={busy || !!active} accept="image/*,video/*,audio/*,.txt,.md" onChange={e => { const files = Array.from(e.target.files || []); perform(async () => {
              const attachments = await uploadFiles(files, uploadSession()); let revision = work.revision;
              for (const attachment of attachments) { const result = await productionCommand(`works/${work.id}/inputs`, { attachment, session_id: uploadSession(), usage, original_audio: originalAudio, interval: originalAudio && sourceStart !== '' && sourceEnd !== '' ? {start:Number(sourceStart),end:Number(sourceEnd)} : null, rights:rightsConfirmed ? {status:'KNOWN',license_name:'用户声明本作品使用权',evidence:[{kind:'user_declaration',reference:'work:'+work.id,summary:'用户明确允许本作品制作使用'}]} : {status:'UNKNOWN'} }, revision); revision = result.revision; }
            }); }} />
          </details>
          <details><summary>本次允许使用的服务</summary><p>选择本次规划、配音或制作允许使用的服务。新增调用可能产生费用。</p>
            {!services.length && <p>尚无可用服务配置。</p>}{services.filter(s => s.provider !== 'unsplash').map(s => { const key = `${s.provider}/${s.model}/${s.mode}`; return <label key={key}><input type="checkbox" disabled={!s.available} checked={approved.includes(key)} onChange={e => setApproved(old => e.target.checked ? [...old,key] : old.filter(k => k !== key))} />{s.label}{!s.available ? '（不可用）' : ''}</label>; })}
          </details>
          {!active && <button disabled={busy} onClick={() => perform(() => command('plans',{generate:true,services:permissions}))}>{latest ? '重新提出创作方案' : '请导演提出完整方案'}</button>}
          {latest && <section><h3>创作方案 · 版本{latest.revision}</h3><p>{latest.plan.summary}</p><p>{latest.plan.settings.duration_seconds}秒 · {latest.plan.settings.aspect_ratio} · {latest.plan.scenes.length}个场景</p>
            <details><summary>展开脚本和场景</summary><p className="preserve-lines">{latest.plan.script}</p>{latest.plan.scenes.map(s => <article key={s.id}><h4>{s.purpose}</h4><p>{s.visual}</p><p>{s.narration}</p></article>)}</details>
            {!latest.confirmed_at && <><button disabled={busy || !!active} onClick={() => setEditing(structuredClone(latest.plan))}>修改方案</button>
              <label><input type="checkbox" checked={allowAI} onChange={e => setAllowAI(e.target.checked)} />外部素材不足时允许 AI 补料</label>
              {allowAI && <div className="production-grid"><label>生图次数上限<input type="number" min={0} value={imageLimit} onChange={e => setImageLimit(Number(e.target.value))} /></label><label>生视频次数上限<input type="number" min={0} value={videoLimit} onChange={e => setVideoLimit(Number(e.target.value))} /></label></div>}
              <button disabled={busy || !!active} onClick={() => perform(() => command(`plans/${latest.revision}/confirm`,{plan_hash:latest.plan_hash,allow_ai:allowAI,image_limit:imageLimit,video_limit:videoLimit,services:permissions}))}>确认完整方案并开始制作</button></>}
          </section>}
          {editing && <section><h3>修改完整方案</h3><label>摘要<textarea value={editing.summary} onChange={e => setEditing({...editing,summary:e.target.value})} /></label><label>脚本<textarea rows={8} value={editing.script} onChange={e => setEditing({...editing,script:e.target.value})} /></label>
            {editing.scenes.map((s,i) => <article key={s.id}><h4>{s.purpose}</h4><label>画面设计<textarea value={s.visual} onChange={e => setEditing({...editing,scenes:editing.scenes.map((v,j) => i === j ? {...v,visual:e.target.value} : v)})} /></label><label>旁白文字<textarea value={s.narration} onChange={e => setEditing({...editing,scenes:editing.scenes.map((v,j) => i === j ? {...v,narration:e.target.value} : v)})} /></label><label>场景时长<input type="number" min={0.1} step={0.1} value={s.duration_seconds || ''} onChange={e => setEditing({...editing,scenes:editing.scenes.map((v,j) => i === j ? {...v,duration_seconds:Number(e.target.value)} : v)})} /></label></article>)}
            <button disabled={busy} onClick={() => perform(async () => { await command('plans',{generate:false,plan:editing}); setEditing(null); })}>保存为新方案版本</button><button onClick={() => setEditing(null)}>放弃修改</button>
          </section>}
          {active && ['needs_decision','failed'].includes(active.state) && <section><h3>补充本次额度</h3><label><input type="checkbox" checked={allowAI} onChange={e => setAllowAI(e.target.checked)} />允许已确认范围内 AI 补料</label><label>生图累计次数上限<input type="number" min={work.quota.IMAGE.limit} value={Math.max(imageLimit,work.quota.IMAGE.limit)} onChange={e => setImageLimit(Number(e.target.value))} /></label><label>生视频累计次数上限<input type="number" min={work.quota.VIDEO.limit} value={Math.max(videoLimit,work.quota.VIDEO.limit)} onChange={e => setVideoLimit(Number(e.target.value))} /></label><p>在对应任务中提交授权后生效；原有已提交次数不清零。</p></section>}
          <section><h3>制作进度</h3>{work.progress?.filter(p => p.run_id === active?.id).map(p => <p role="status" key={p.kind}>{p.kind === 'quality_progress' ? `已审查 ${p.detail.completed_segments}/${p.detail.total_segments} 段实际视频` : `视频合成：${p.detail.stage || '进行中'} · ${p.detail.completed_steps}/${p.detail.total_steps} 步`}</p>)}{work.tasks.length === 0 && <p>等待开始创作。</p>}
            {work.tasks.map(task => <details key={task.id}><summary>{taskLabels[task.kind] || task.kind} · {stateLabels[task.state] || task.state}</summary>
              {task.error_json && <p>{(() => { try { return JSON.parse(task.error_json).user_message || '需要处理'; } catch { return '需要处理'; } })()}</p>}
              {['needs_decision','failed'].includes(task.state) && <><p>先补充所需输入或服务授权，再继续本步。</p><button disabled={busy} onClick={() => perform(() => command('authorization-grants',{purpose:active?.kind === 'planning' ? 'planning' : 'production',services:permissions,allow_ai:allowAI,image_limit:Math.max(imageLimit,work.quota.IMAGE.limit),video_limit:Math.max(videoLimit,work.quota.VIDEO.limit)}))}>提交本次授权或追加额度</button><button disabled={busy} onClick={() => perform(() => command('resume',{decision_id:task.id}))}>继续这一步</button></>}
            </details>)}
            {Object.entries(work.quota).map(([kind,q]) => <p key={kind}>{kind === 'IMAGE' ? '生图' : '生视频'}：已提交 {q.used}，待核实 {q.unknown}，预留 {q.reserved}，可用 {q.available}</p>)}
            {active && <button disabled={busy} onClick={() => perform(() => command('cancel',{}))}>取消后续制作，保留已有成果</button>}
          </section>
          {active && ['revision','production'].includes(active.kind) && active.state === 'needs_decision' && work.reviews?.slice(0,1).filter(r => r.changes.summary).map(r => <section key={r.id}><h3>修订影响确认</h3><p>{r.changes.summary}</p><p>{r.changes.reason}</p><p>{r.changes.requires_new_generation ? '需要取得新素材；重新确认方案时明确生成次数，未授权不会调用。' : '保留未受影响的素材和历史版本。'}</p><button disabled={busy} onClick={() => perform(() => command('revisions/confirm',{review_id:r.id,change_hash:r.change_hash,services:permissions}))}>同意上述范围，请提出修订方案</button></section>)}
          <section><h3>作品版本</h3><button disabled={busy} onClick={() => perform(async () => setDeletion(await productionRequest(`works/${work.id}/deletion-preview`)))}>查看删除作品影响</button>
            {deletion && <div role="alert"><p>将删除{deletion.output_id ? '所选历史版本' : '整部作品'}，涉及 {deletion.artifact_ids.length} 项成果；保留 {deletion.preserved_artifact_ids.length} 项共享引用。{deletion.clears_acceptance ? '这会移除当前已接受版本，不自动选择其他版本。' : ''}{deletion.deferred_cleanup ? '在途操作或共享引用仍存在，文件清理将延后。' : ''}</p><button onClick={() => setDeletion(null)}>保留，不删除</button><button disabled={busy} onClick={() => perform(async () => { await productionCommand(`works/${work.id}/delete`,{preview_hash:deletion.preview_hash,output_id:deletion.output_id},deletion.expected_revision);if (!deletion.output_id){selectedRef.current='';setSelected('');}setDeletion(null); })}>确认删除上述范围</button></div>}{outputs.length === 0 && <p>有可播放成果后将在这里展示。</p>}
            {outputs.map(output => <article key={output.id}><h4>版本{output.output_revision} · {output.quality_state === 'passed' ? '自检通过' : '待修预览'}{work.accepted_output_id === output.id ? ' · 已接受' : ''}</h4><video controls preload="metadata" src={artifactURL(output.id)} />
              <button disabled={busy || output.quality_state !== 'passed'} onClick={() => perform(() => command(`outputs/${output.id}/accept`,{}))}>接受此版本并保存</button><a href={artifactURL(output.export_artifact_id || output.id)} download>{output.export_artifact_id && output.export_artifact_id !== output.id ? '导出视频及素材署名包' : '导出视频'}</a><button disabled={busy} onClick={() => perform(async () => setDeletion(await productionRequest(`works/${work.id}/deletion-preview?output_id=${output.id}`)))}>查看删除此版本影响</button><button onClick={() => setCompare(compare === output.id ? '' : output.id)}>选作比较版本</button><button disabled={busy} onClick={() => perform(async () => { const r = await command('fork',{session_id:uploadSession(),output_id:output.id});if(r.work_id)setSelected(r.work_id); })}>基于此版本创作新作品</button>
              <label>对这个版本的修改意见<textarea value={feedback} onChange={e => setFeedback(e.target.value)} placeholder="例如：只把第二幕字幕放大，保留其他部分" /></label><button disabled={busy || !feedback.trim()} onClick={() => perform(() => command('revisions',{output_id:output.id,feedback}))}>按意见局部修改</button>
            </article>)}
            {work.artifacts.filter(a => a.kind === 'export_bundle').map(a => <p key={a.id}><a href={artifactURL(a.id)} download>下载视频与必须保留的素材署名包</a></p>)}
            {compare && <div className="production-compare"><h4>比较版本</h4><video controls src={artifactURL(compare)} /></div>}
          </section>
        </>}
        <details><summary>频道与导演</summary><label>名称<input value={catalogName} onChange={e => setCatalogName(e.target.value)} /></label>
          <button disabled={busy || !profile || !catalogName} onClick={() => perform(() => productionCommand('channels',{name:catalogName,profile_ref:profile}))}>为选用画像创建频道</button>
          {work && <fieldset><legend>本次用于形成导演的参考视频</legend>{work.inputs.filter(i => i.kind === 'video').map(i => <label key={i.id}><input type="checkbox" checked={directorReferences.includes(i.id)} onChange={e => setDirectorReferences(old => e.target.checked ? [...old,i.id] : old.filter(id => id !== i.id))} />{i.original_name || i.id}</label>)}</fieldset>}
          {work && <button disabled={busy || !!active || !catalogName || !work.inputs.some(i => i.kind === 'video' && directorReferences.includes(i.id))} onClick={() => perform(() => productionCommand('directors',{name:catalogName,work_id:work.id,work_revision:work.revision,services:permissions,reference_input_ids:work.inputs.filter(i => i.kind === 'video' && directorReferences.includes(i.id)).map(i => i.id)}))}>用本作品参考视频形成导演</button>}
          {channels.map(c => <article key={c.id}><strong>{c.name} · {c.profile_name}</strong>
            <button disabled={!catalogName || busy} onClick={() => perform(() => productionCommand(`channels/${c.id}`,{name:catalogName},c.revision,'PATCH'))}>用上方名称重命名</button>
            <details><summary>关联导演与默认搭配</summary>{directors.filter(d => !d.archived).map(d => <label key={d.id}><input type="checkbox" checked={c.director_ids.includes(d.id)} onChange={e => perform(() => productionCommand(`channels/${c.id}`,{director_ids:e.target.checked ? [...c.director_ids,d.id] : c.director_ids.filter(id => id !== d.id),default_director_revision:null},c.revision,'PATCH'))} />{d.name}</label>)}
              <select aria-label={`${c.name}默认导演`} value={c.default_director_revision || ''} onChange={e => perform(() => productionCommand(`channels/${c.id}`,{default_director_revision:e.target.value || null},c.revision,'PATCH'))}><option value="">无默认导演</option>{directors.filter(d => c.director_ids.includes(d.id)).flatMap(d => d.versions.filter(v => v.accepted_at).map(v => <option key={v.id} value={v.id}>{d.name} · 版本{v.revision}</option>))}</select>
            </details><button onClick={() => perform(() => productionCommand(`channels/${c.id}`,{archived:!c.archived},c.revision,'PATCH'))}>{c.archived ? '恢复频道' : '归档频道'}</button></article>)}
          {directors.map(d => <article key={d.id}><strong>{d.name}</strong><button disabled={!catalogName || busy} onClick={() => perform(() => productionCommand(`directors/${d.id}`,{name:catalogName},d.revision,'PATCH'))}>用上方名称重命名</button><button onClick={() => perform(() => productionCommand(`directors/${d.id}`,{archived:!d.archived},d.revision,'PATCH'))}>{d.archived ? '恢复导演' : '归档导演'}</button>{d.versions.map(v => <div key={v.id}><p>版本{v.revision} · {v.accepted_at ? '已接受' : v.style_confirmed ? '待试片' : '待确认风格'}</p><p>{String(v.style.visual_style || '')}</p><p>{String(v.style.storytelling || '')}</p>
            <details><summary>拆解依据与完整风格</summary>{Object.entries(v.style).filter(([key]) => key !== 'schema_version').map(([key,value]) => <p key={key}>{key}：{Array.isArray(value) ? value.join('；') : String(value)}</p>)}<p>参考证据 {v.evidence.length} 项，后续风格版本保留来源。</p></details>
            <details><summary>调整风格并保存新版本</summary><label>视听风格<textarea value={directorEdits[v.id]?.visual_style ?? String(v.style.visual_style || '')} onChange={e => setDirectorEdits(old => ({...old,[v.id]:{visual_style:e.target.value,storytelling:old[v.id]?.storytelling ?? String(v.style.storytelling || '')}}))} /></label><label>讲述方式<textarea value={directorEdits[v.id]?.storytelling ?? String(v.style.storytelling || '')} onChange={e => setDirectorEdits(old => ({...old,[v.id]:{storytelling:e.target.value,visual_style:old[v.id]?.visual_style ?? String(v.style.visual_style || '')}}))} /></label><button disabled={busy || !directorEdits[v.id]} onClick={() => perform(() => productionCommand(`directors/${d.id}/revisions`,{style:{...v.style,...directorEdits[v.id]},evidence:v.evidence},d.revision))}>保存新风格版本，保留原版</button></details>
            <button disabled={busy || !v.style_confirmed || d.archived} onClick={() => { setSelected('');setDirector(v.id);setTrial(true); }}>用此风格创建试片</button>
            {v.style_confirmed && !v.accepted_at && trialOutputs(work,v.id).map(o => <button key={o.id} disabled={busy} onClick={() => perform(() => productionCommand(`directors/${d.id}/accept`,{revision_id:v.id,trial_artifact_id:o.id},d.revision))}>以当前作品版本{o.output_revision}接受导演（须使用此风格）</button>)}
            {!v.style_confirmed && <button onClick={() => perform(() => productionCommand(`directors/${d.id}`,{revision_id:v.id,style_confirmed:true},d.revision,'PATCH'))}>确认风格，准备试片</button>}
          </div>)}</article>)}
        </details>
      </main>
    </div>
  </div>;
}
