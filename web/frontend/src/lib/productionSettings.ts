import type { VideoSettings } from './productionApi';

export type VoiceIdentity = NonNullable<VideoSettings['voice']>;
export type Subtitles = NonNullable<VideoSettings['subtitles']>;
export type SettingsScope = 'work' | 'channel' | 'profile';
export interface VoiceOption {
  identity: VoiceIdentity; label: string; tags: string[]; languages: string[];
  speed_range: [number, number] | null; instructions_supported: boolean; available: boolean;
  unavailable_reason: string; fee_notice: string;
  service: { provider: string; model: string; mode: string };
}
export interface SettingsPreview {
  kind: 'voice' | 'subtitles'; url?: string; message?: string; reused?: boolean;
}
export const defaultSubtitles: Subtitles = {
  enabled: true, font: 'sans-serif', size: 48, color: '#FFFFFF', outline: '#000000',
  background: 'transparent', position: 'bottom',
};
export const voiceKey = (voice?: VoiceIdentity | null) => voice
  ? JSON.stringify([voice.provider, voice.model, voice.engine, voice.voice_id]) : '';

export function resolveSettings(profile: Partial<VideoSettings> = {}, channel: Partial<VideoSettings> = {},
  work: Partial<VideoSettings> = {}): Partial<VideoSettings> {
  let result: Partial<VideoSettings> = {};
  for (const source of [profile, channel, work]) {
    result = { ...result, ...structuredClone(source),
      ...('subtitles' in source ? { subtitles: { ...defaultSubtitles, ...result.subtitles, ...source.subtitles } } : {}) };
  }
  return result;
}

export function chooseVoice(settings: VideoSettings, options: VoiceOption[], key: string): VideoSettings {
  if (!key) return { ...settings, voice: null };
  const option = options.find(item => voiceKey(item.identity) === key);
  if (!option?.available) throw new Error('所选声音不可用，原设置已保留');
  return { ...settings, voice: structuredClone(option.identity) };
}

export function saveSettingsPayload(scope: SettingsScope, settings: VideoSettings,
  available: { channel: boolean; profile: boolean }) {
  if (!['work', 'channel', 'profile'].includes(scope)) throw new Error('请选择保存范围');
  if (scope !== 'work' && !available[scope]) throw new Error(`本作品尚未选择${scope === 'channel' ? '频道' : '画像'}`);
  return { scope, settings: structuredClone(settings) };
}
