import { enterVideo, videoRequest, type ConversationView, type VideoEntry } from './conversationApi';

export const CONFIGURATION_PROMPTS = {
  channel_create: {
    create: '我想创建一个频道，请根据已有画像和我讨论名称、定位、主题与受众，整理未保存的提案，等我确认再保存。',
    edit: '我想修改当前选定的频道，请先展示现有配置，与我讨论需要改动的部分，等我确认再保存，不创建新频道，也不修改画像。',
  },
  director_formation: {
    create: '我想从参考视频创建一个导演，请先讨论参考和风格目标；参考分析、风格保存和试片制作分别等我确认。',
    edit: '我想修改当前选定的导演风格，请读取现有版本和参考依据，讨论后另存新版本，不覆盖旧版本，不自动分析参考或制作试片。',
  },
};

export const CONVERSATION_WORKFLOWS = [
  { kind: 'new_work', label: '视频创作', aliases: '视频产线 视频管线 做视频',
    desc: '讨论主题与素材 → 确认完整方案 → 成片、审片与修改',
    prompt: '我想创作一条视频，请先和我讨论本期主题、素材和风格，整理草稿；完整方案和制作都等我确认。' },
  { kind: 'director_formation', label: '导演', aliases: '创建导演 修改导演 参考拆解 风格 试片',
    desc: '创建或修改导演 → 讨论参考与风格 → 确认保存版本',
    prompt: CONFIGURATION_PROMPTS.director_formation.create },
  { kind: 'channel_create', label: '频道', aliases: '创建频道 修改频道 定位 受众 栏目',
    desc: '创建或修改频道 → 讨论定位与默认配置 → 确认保存',
    prompt: CONFIGURATION_PROMPTS.channel_create.create },
] as const;

export type ConversationWorkflowKind = typeof CONVERSATION_WORKFLOWS[number]['kind'];

export function replaceWorkflowPrompt(prompt: string, draft: string): string {
  // Replace only our generated starter when choosing another flow; keep the
  // Creator's topic/edits rather than stacking contradictory menu prompts.
  const starters = [...CONVERSATION_WORKFLOWS.map(w=>w.prompt), ...Object.values(CONFIGURATION_PROMPTS).flatMap(p=>Object.values(p))];
  const old = starters.find(prompt => draft === prompt || draft.startsWith(prompt + '\n\n'));
  const content = old ? draft.slice(old.length).replace(/^\n\n/, '') : draft;
  return prompt + (content.trim() ? '\n\n' + content : '');
}

export function workflowDraft(kind: ConversationWorkflowKind, draft: string): string {
  return replaceWorkflowPrompt(CONVERSATION_WORKFLOWS.find(w => w.kind === kind)!.prompt, draft);
}

export async function enterConversationWorkflow(session: {id: string; persona?: string; videoSegmentId?: string}, kind: ConversationWorkflowKind) {
  const current = session.videoSegmentId ? await videoRequest<ConversationView>(encodeURIComponent(session.id)) : undefined;
  const context = current?.context;
  const entry: VideoEntry = { kind, profile_ref: context ? context.profile_ref || undefined : session.persona || undefined };
  if (kind !== 'channel_create' && context?.channel_id) entry.channel_id = context.channel_id;
  if (kind === 'new_work' && context?.settings) {
    const settings = context.settings as Record<string, unknown>;
    if (typeof settings.director_revision === 'string') {
      entry.director_revision = settings.director_revision;
      entry.director_trial = settings.director_trial === true;
    }
  }
  // Only /enter; no chat send, Work creation, catalog save or production call.
  return enterVideo(session.id, entry);
}
