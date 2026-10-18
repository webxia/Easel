import { useEffect, useMemo, useRef, useState } from 'react';
import { CAPABILITY_MENU } from '../lib/capabilityMenu';
import type { CapabilityItem } from '../lib/capabilityMenu';
import { CONVERSATION_WORKFLOWS, type ConversationWorkflowKind } from '../lib/conversationWorkflows';

const DOT: Record<string, string> = { done: 's-done', ready: 's-ready', need: 's-need', incoming: 's-incoming' };

/** 笔入口：管线先绑定当前对话再预填，普通能力直接预填；均不自动发送。 */
export default function BrushEntry({ onPick, onVideo, disabled=false, videoMode=false }: { onPick: (text: string) => void; onVideo?:(kind:ConversationWorkflowKind)=>void|Promise<void>; disabled?:boolean; videoMode?:boolean }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState(0);
  const [q, setQ] = useState('');
  const [entering, setEntering] = useState(false);
  const [error, setError] = useState('');
  const wrapRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (open) searchRef.current?.focus(); }, [open]);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const all = useMemo(
    () => CAPABILITY_MENU.tabs.flatMap((t) => t.groups.flatMap((g) => g.items)),
    [],
  );
  const pipeline = useMemo(() => all.find((x) => x.status === 'incoming'), [all]);

  const ql = q.trim().toLowerCase();
  const hit = (it: CapabilityItem) => !ql || `${it.label}${it.desc || ''}${it.skill || ''}`.toLowerCase().includes(ql);

  const pick = (it: CapabilityItem, pipe?: boolean) => {
    onPick(pipe ? '用「视频产线」做一支整片：' : `帮我做「${it.label}」`);
    setOpen(false);
  };
  const pickWorkflow = async (kind:ConversationWorkflowKind) => {
    if(entering||disabled||!onVideo)return;
    setEntering(true);setError('');
    try { await onVideo(kind);setOpen(false); }
    catch(e) { setError((e as Error).message); }
    finally { setEntering(false); }
  };
  const workflows = CONVERSATION_WORKFLOWS.filter(w=>!ql||`${w.label}${w.desc}${w.aliases}`.toLowerCase().includes(ql));

  return (
    <div className={`brush-entry${open ? ' open' : ''}`} ref={wrapRef}>
      <button type="button" className="brush-btn" disabled={disabled||entering} onClick={() => setOpen((v) => !v)}
        aria-label="看看能做什么" title="看看能做什么">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <defs>
            <linearGradient id="brushHandleGrad" x1="12" y1="1.6" x2="12" y2="11.6" gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor="#8adfce" /><stop offset="1" stopColor="#45b0b4" />
            </linearGradient>
            <linearGradient id="brushTipGrad" x1="12" y1="13.2" x2="12" y2="22.6" gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor="#2f6fae" /><stop offset="1" stopColor="#222e83" />
            </linearGradient>
          </defs>
          <g transform="rotate(45 12 12)">
            <rect x="11.15" y="1.6" width="1.7" height="10" rx=".85" fill="url(#brushHandleGrad)" />
            <rect x="10.6" y="11.5" width="2.8" height="1.75" rx=".6" fill="#b9e3d9" stroke="#7fb3aa" strokeWidth=".3" />
            <path d="M10.7 13.2 C9.95 16.6 10.2 19.9 11.95 22.6 C13.7 19.9 13.95 16.6 13.2 13.2 Z" fill="url(#brushTipGrad)" />
            <path d="M11.95 13.6 L11.95 21.2" stroke="#1d2c6f" strokeWidth=".4" strokeLinecap="round" opacity=".38" />
          </g>
        </svg>
        <span className="brush-mark" aria-hidden="true" />
        <span className="brush-tip">看看能做什么</span>
      </button>

      {open && (
        <div className="brush-panel" role="dialog" aria-label="能做的都在这">
          <div className="brush-panel-head">
            <div className="brush-panel-headline">
              <div className="brush-panel-title">能做的都在这</div>
              <div className="brush-panel-sub">{onVideo?'选择管线 → 当前对话继续；引导语可编辑后发送':'选一个 → 自动填进输入框；「管线」件走整片产线'}</div>
            </div>
            <input ref={searchRef} className="brush-search" placeholder="搜索…" value={q}
              onChange={(e) => setQ(e.target.value)} />
            <button type="button" className="brush-close" onClick={() => setOpen(false)} aria-label="关闭">×</button>
          </div>
          <div className="brush-tabs">
            {CAPABILITY_MENU.tabs.map((t, i) => (
              <button type="button" key={t.id} className={`brush-tab${i === tab ? ' on' : ''}`}
                onClick={() => setTab(i)}>{t.label}</button>
            ))}
          </div>
          <div className="brush-body">
            {error&&<p role="alert">{error}</p>}
            {onVideo&&workflows.length>0&&<div className="brush-grp" aria-label="创作管线">
              <div className="brush-grp-name">我们的创作管线 · 画像、导演与频道</div>
              {workflows.map(w=><button type="button" key={w.kind} aria-label={w.label} disabled={disabled||entering} className="brush-item brush-item-pipe" onClick={()=>void pickWorkflow(w.kind)}>
                <span className="brush-dot s-ready"/><span className="brush-il">{w.label}</span><span className="brush-chip-pipe">管线</span><span className="brush-idesc">{w.desc}</span><span className="brush-iadd">＋</span>
              </button>)}
            </div>}
            {videoMode&&<p>当前对话使用作品管线。原片包装及其他 Easel 技能请在新对话使用。</p>}
            {!videoMode&&pipeline && hit(pipeline) && (
              <div className="brush-grp">
                <div className="brush-grp-name">Easel 原有管线 · 原片包装</div>
                <button type="button" className="brush-item brush-item-pipe" onClick={() => pick(pipeline, true)}>
                  <span className={`brush-dot ${DOT[pipeline.status || 'ready'] || 's-ready'}`} />
                  <span className="brush-il">原片包装</span>
                  <span className="brush-chip-pipe">原产线</span>
                  <span className="brush-idesc">已有整条原片 → 分场、动效、字幕与调色；按原技能流程执行</span>
                  <span className="brush-iadd">＋</span>
                </button>
              </div>
            )}
            {!videoMode&&CAPABILITY_MENU.tabs[tab] && CAPABILITY_MENU.tabs[tab].groups.map((g) => {
              const items = g.items.filter((it) => it.status !== 'incoming' && hit(it));
              if (!items.length) return null;
              return (
                <div key={g.label} className="brush-grp">
                  <div className="brush-grp-name">{g.label} · {items.length}</div>
                  {items.map((it) => (
                    <button type="button" disabled={disabled||entering} key={it.skill || it.label} className="brush-item" onClick={() => pick(it)}>
                      <span className={`brush-dot ${DOT[it.status || 'ready'] || 's-ready'}`} />
                      <span className="brush-il">{it.label}</span>
                      <span className="brush-idesc">{it.desc}</span>
                      <span className="brush-iadd">＋</span>
                    </button>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
