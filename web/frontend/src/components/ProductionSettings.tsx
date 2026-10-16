import { useState } from 'react';
import type { VideoSettings } from '../lib/productionApi';
import { chooseVoice, defaultSubtitles, saveSettingsPayload, voiceKey } from '../lib/productionSettings';
import type { SettingsPreview, SettingsScope, VoiceOption } from '../lib/productionSettings';

export interface ProductionSettingsProps {
  settings: VideoSettings;
  voices: VoiceOption[];
  fonts: { id: string; label: string }[];
  availableScopes?: { channel: boolean; profile: boolean };
  disabled?: boolean;
  onChange: (settings: VideoSettings) => void;
  onPreview: (kind: 'voice' | 'subtitles', settings: VideoSettings, text: string, options?: { regenerate?: boolean }) => Promise<SettingsPreview>;
  onSave: (scope: SettingsScope, settings: VideoSettings) => Promise<unknown>;
}

export default function ProductionSettings({ settings, voices, fonts, availableScopes = { channel: false, profile: false },
  disabled = false, onChange, onPreview, onSave }: ProductionSettingsProps) {
  const [scope, setScope] = useState<SettingsScope>('work');
  const [text, setText] = useState('用同一段文字，试听与当前人设相符的表达。');
  const [preview, setPreview] = useState<SettingsPreview | null>(null);
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState('');
  const currentKey = voiceKey(settings.voice);
  const selected = voices.find(item => voiceKey(item.identity) === currentKey);
  const subtitles = { ...defaultSubtitles, ...settings.subtitles };
  const change = (next: VideoSettings) => { onChange(next); setPreview(null); setMessage('设置尚未保存'); };
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true); setMessage('');
    try { await action(); } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  };
  const subtitleChange = (patch: Partial<typeof subtitles>) => change({ ...settings, subtitles: { ...subtitles, ...patch } });
  return <section className="production-settings" aria-label="旁白与字幕设置">
    <h3>旁白与字幕</h3>
    <fieldset disabled={disabled || busy}>
      <legend>固定旁白</legend>
      <label>声音<select value={currentKey} onChange={event => {
        try { change(chooseVoice(settings, voices, event.target.value)); } catch (error) { setMessage(String(error)); }
      }}><option value="">不固定声音</option>
        {!!currentKey && !selected && <option value={currentKey}>当前固定声音（服务暂不可用）</option>}
        {voices.map(option => <option key={voiceKey(option.identity)} value={voiceKey(option.identity)} disabled={!option.available}>{option.label}{!option.available ? '（不可用）' : ''}</option>)}
      </select></label>
      {settings.voice && (!selected || !selected.available) && <p role="status">固定声音暂不可用，原设置已保留。请选择其他声音后试听；不会自动替换。</p>}
      {selected?.speed_range && settings.voice && <label>语速<input type="number" step="0.05" min={selected.speed_range[0]} max={selected.speed_range[1]} value={Number(settings.voice.parameters.speed ?? 1)} onChange={event => change({ ...settings, voice: { ...settings.voice!, parameters: { ...settings.voice!.parameters, speed: Number(event.target.value) } } })} /></label>}
      {selected?.instructions_supported && settings.voice && <label>声音表达要求<input value={String(settings.voice.parameters.instructions ?? '')} maxLength={1000} onChange={event => change({ ...settings, voice: { ...settings.voice!, parameters: { ...settings.voice!.parameters, instructions: event.target.value } } })} placeholder="例如：自然、平静，像向朋友解释" /></label>}
      <label>试听文字 / 字幕预览文字<textarea value={text} maxLength={12000} onChange={event => { setText(event.target.value); setPreview(null); }} rows={3} /></label>
      <p>{selected?.fee_notice || '新试听可能产生服务费用；同文同音色已生成的音频可以复用。配音不占生图或生视频次数。'}</p>
      <button type="button" disabled={!selected?.available || !text.trim()} onClick={() => run(async () => setPreview(await onPreview('voice', settings, text)))}>试听当前声音</button>
      <button type="button" disabled={!selected?.available || !text.trim()} onClick={() => run(async () => setPreview(await onPreview('voice', settings, text, { regenerate: true })))}>重新生成试听（新增调用）</button>
    </fieldset>
    <fieldset disabled={disabled || busy}>
      <legend>字幕样式</legend>
      <label><input type="checkbox" checked={subtitles.enabled} onChange={event => subtitleChange({ enabled: event.target.checked })} />显示字幕</label>
      <label>字体<select value={subtitles.font} onChange={event => subtitleChange({ font: event.target.value })}>
        {!fonts.some(font => font.id === subtitles.font) && <option value={subtitles.font}>{subtitles.font}（当前不可用）</option>}
        {fonts.map(font => <option value={font.id} key={font.id}>{font.label}</option>)}
      </select></label>
      <label>字号<input type="number" min={1} max={1080} value={subtitles.size} onChange={event => subtitleChange({ size: Number(event.target.value) })} /></label>
      <label>文字颜色<input type="color" value={subtitles.color} onChange={event => subtitleChange({ color: event.target.value })} /></label>
      <label><input type="checkbox" checked={subtitles.outline !== 'transparent'} onChange={event => subtitleChange({ outline: event.target.checked ? '#000000' : 'transparent' })} />描边</label>
      {subtitles.outline !== 'transparent' && <label>描边颜色<input type="color" value={subtitles.outline} onChange={event => subtitleChange({ outline: event.target.value })} /></label>}
      <label><input type="checkbox" checked={subtitles.background !== 'transparent'} onChange={event => subtitleChange({ background: event.target.checked ? '#000000' : 'transparent' })} />字幕背景</label>
      {subtitles.background !== 'transparent' && <label>背景颜色<input type="color" value={subtitles.background.slice(0, 7)} onChange={event => subtitleChange({ background: event.target.value })} /></label>}
      <label>位置<select value={subtitles.position} onChange={event => subtitleChange({ position: event.target.value as typeof subtitles.position })}><option value="top">顶部</option><option value="middle">中间</option><option value="bottom">底部</option></select></label>
      <button type="button" disabled={!text.trim()} onClick={() => run(async () => setPreview(await onPreview('subtitles', settings, text)))}>在当前画面预览</button>
    </fieldset>
    {preview?.url && (preview.kind === 'voice' ? <audio controls src={preview.url} /> : <img src={preview.url} alt="当前画面的字幕预览" style={{ maxWidth: '100%', maxHeight: 480 }} />)}
    {preview?.message && <p role="status">{preview.message}</p>}
    {preview?.reused && <p>已复用现有结果。</p>}
    <label>保存范围<select disabled={disabled || busy} value={scope} onChange={event => setScope(event.target.value as SettingsScope)}><option value="work">仅本片</option><option value="channel" disabled={!availableScopes.channel}>当前频道默认</option><option value="profile" disabled={!availableScopes.profile}>当前画像默认</option></select></label>
    <button type="button" disabled={disabled || busy} onClick={() => run(async () => {
      const payload = saveSettingsPayload(scope, settings, availableScopes);
      await onSave(payload.scope, payload.settings); setMessage('已保存所选范围；历史方案保持原设置。');
    })}>保存设置</button>
    {message && <p role="status">{message}</p>}
  </section>;
}
