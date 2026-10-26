import { useEffect, useState } from 'react';
import { artifactURL, productionRequest, workLabels, type Work } from '../lib/productionApi';
import { libraryOutputs, libraryRelatedFiles, libraryVersionPlan, selectedLibraryOutput, type LibraryWork } from '../lib/contentLibrary';
import { openPublishSource, openPublicationDraft, publicationStatus, type Publication } from '../lib/publicationApi';
import type { VideoEntry } from '../lib/conversationApi';
import { IconChevron, IconRefresh, IconTrash } from './icons';

interface Props {
  item: LibraryWork; onBack: () => void; onContinue?: (entry: VideoEntry) => void;
  onDelete: (item: LibraryWork) => void; deleting: boolean;
}

export default function LibraryWorkDetail({ item, onBack, onContinue, onDelete, deleting }: Props) {
  const [work, setWork] = useState<Work | null>(null);
  const [publications, setPublications] = useState<Publication[]>([]);
  const [selected, setSelected] = useState<string | undefined>(item.artifact_id || undefined);
  const [error, setError] = useState('');
  const [publicationError, setPublicationError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [recordsLoaded, setRecordsLoaded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setError(''); setPublicationError(''); setRecordsLoaded(false);
    // Browsing never enters a conversation, prepares a draft or queries a platform.
    productionRequest<Work>(`works/${encodeURIComponent(item.work_id)}`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setWork(value); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    productionRequest<Publication[]>(`publications?work_id=${encodeURIComponent(item.work_id)}`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) { setPublications(value); setRecordsLoaded(true); } })
      .catch(e => { if (!controller.signal.aborted) setPublicationError(e.message); });
    return () => controller.abort();
  }, [item.work_id, refresh]);

  const output = work ? selectedLibraryOutput(work, selected) : undefined;
  const outputs = work ? libraryOutputs(work) : [];
  const versionPlan = work ? libraryVersionPlan(work, output) : undefined;
  const currentPlan = work?.plans.find(p => p.revision === work.current_plan_revision);
  const records = publications.filter(p => p.output_id === output?.id);
  const related = work ? libraryRelatedFiles(work) : [];
  const continueWork = () => onContinue?.({ work_id: item.work_id, ...(output ? { output_id: output.id } : {}), kind: 'continue' });

  return <section className="library-work-detail" aria-label="作品详情">
    <div className="gallery-filters">
      <button className="btn btn-sm" onClick={onBack}><IconChevron size={13} /> 返回内容库</button>
      <button className="btn btn-sm" onClick={() => setRefresh(n => n + 1)}><IconRefresh size={13} /> 刷新详情</button>
    </div>
    {error && <div className="notice-error" role="alert">{error}</div>}
    {!work && !error && <p role="status">正在读取作品…</p>}
    {work && <>
      <div className="library-detail-heading"><h2>{work.title}</h2><span>{workLabels[work.state] || '创作中'}</span></div>
      <section className="card library-detail-section">
        <h3>{output ? `版本 ${output.output_revision} · ${output.id === work.accepted_output_id ? '已接受成片' : '尚未接受的预览'}` : '尚未生成视频'}</h3>
        {output ? <>
          <video key={output.id} controls preload="metadata" src={artifactURL(output.id)} />
          <p>{output.delivery?.message || '请查看实际检查结果，并在创作对话中审阅此版本。'}</p>
          <div className="library-detail-actions">
            <a className="btn btn-sm" href={artifactURL(output.id)} download>下载此版视频</a>
            {output.export_artifact_id && output.export_artifact_id !== output.id && <a className="btn btn-sm" href={artifactURL(output.export_artifact_id)} download>下载视频与署名</a>}
          </div>
          {!!output.checks?.length && <details><summary>此版本检查结果</summary>{output.checks.map((c, i) => <p key={i}>{({ technical: '技术检查', visual: '画面检查', semantic: '内容检查', audio: '声音检查' } as Record<string, string>)[c.kind] || '成片检查'}：{({ pass: '通过', fail: '未通过', not_tested: '未验证', partial: '部分完成' } as Record<string, string>)[c.status] || '未验证'}</p>)}</details>}
        </> : <p>方案及已保存成果保留，可在创作对话中查看进度。</p>}
      </section>
      {!!outputs.length && <section className="library-detail-section"><h3>版本</h3><div className="gallery-filters">{outputs.map(o => <button className={`chip ${o.id === output?.id ? 'active' : ''}`} key={o.id} onClick={() => setSelected(o.id)}>版本 {o.output_revision}{o.id === work.accepted_output_id ? ' · 已接受' : ' · 预览'}</button>)}</div></section>}
      <section className="library-detail-section"><h3>创作信息</h3>
        {versionPlan ? <details><summary>此版本方案 · 第 {versionPlan.revision} 版{versionPlan.confirmed_at ? ' · 已确认' : ''}</summary><p>{versionPlan.plan.summary}</p><div className="library-script">{versionPlan.plan.script}</div></details> : <p>未记录可直接关联此版本的方案。</p>}
        {currentPlan && currentPlan !== versionPlan && <details><summary>当前作品信息 · 方案第 {currentPlan.revision} 版</summary><p>此信息不代表所选历史版本的制作依据。</p><p>{currentPlan.plan.summary}</p></details>}
        <p>频道、导演与素材来源可在创作对话或导出署名中查看。</p>
      </section>
      {!!related.length && <details className="library-detail-section"><summary>相关文件 · {related.length}</summary><p>以下为作品级文件；各版本交付请使用上方对应下载入口。</p><ul>{related.map((a, index) => <li key={a.id}><a href={artifactURL(a.id)} target="_blank" rel="noreferrer">{a.kind === 'export_bundle' ? '视频与署名包' : ({ voice: '配音', subtitles: '字幕', image: '图片', audio: '音频' } as Record<string, string>)[a.kind] || '相关媒体或文档'} · {index + 1}{a.output_revision != null ? ` · 版本 ${a.output_revision}` : ''}</a></li>)}</ul></details>}
      <section className="library-detail-section"><h3>发布</h3>
        {output?.delivery?.can_publish && records.length>0&&<button className="btn btn-sm" onClick={()=>openPublishSource(item.work_id,output.id)}>选择其他平台</button>}
        {publicationError ? <div className="notice-error" role="alert">发布记录读取失败：{publicationError}。请刷新后核实。</div> : !recordsLoaded ? <p>正在读取发布记录…</p> : records.length ? records.map(p => <div className="library-publication" key={p.id}><span>{({bilibili:'B站',douyin:'抖音',xiaohongshu:'小红书',kuaishou:'快手','weixin-channels':'视频号'} as Record<string,string>)[p.platform||'bilibili']||p.platform} · {publicationStatus(p)}</span><button className="btn btn-sm" onClick={() => openPublicationDraft(p.id)}>查看发布草稿或记录</button></div>) : output?.delivery?.can_publish ? <button className="btn btn-sm" disabled={busy} onClick={async () => { setBusy(true); try { openPublishSource(item.work_id, output.id); } catch (e) { setPublicationError((e as Error).message); } finally { setBusy(false); } }}>准备发布</button> : <p>接受具体成片版本后，可准备发布；接受和投稿在现有流程中分别确认。</p>}
      </section>
      <div className="library-detail-actions">
        {onContinue && <button className="btn btn-primary btn-sm" onClick={continueWork}>{output ? '围绕此版本继续创作' : '继续创作'}</button>}
        <button className="btn btn-sm btn-danger" disabled={deleting} onClick={() => onDelete(item)}><IconTrash size={13} /> 删除整部作品</button>
      </div>
      <p className="library-detail-hint">继续创作会打开关联此作品的对话，不会自动恢复制作。可在对话中审阅、接受或提出修改。</p>
    </>}
  </section>;
}
