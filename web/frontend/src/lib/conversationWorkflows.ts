import { enterVideo, videoRequest, type ConversationView, type VideoEntry } from './conversationApi';

export const CONVERSATION_WORKFLOWS = [
  { kind: 'new_work', label: '视频创作', aliases: '视频产线 视频管线 做视频',
    desc: '讨论主题与素材 → 确认完整方案 → 成片、审片与修改',
    prompt: '我想创作一条视频，请先和我讨论本期主题、素材和风格，整理草稿；完整方案和制作都等我确认。' },
  { kind: 'director_formation', label: '创建导演', aliases: '导演 参考拆解 风格 试片',
    desc: '讨论参考与风格 → 确认分析 → 风格草稿、试片与接受',
    prompt: '我想用参考视频创建一个导演，请先和我讨论参考素材和风格目标；分析、试片和保存都等我确认。' },
  { kind: 'channel_create', label: '创建频道', aliases: '频道 定位 受众 栏目',
    desc: '讨论名称与定位 → 确认保存 → 衔接本期视频创作',
    prompt: '我想创建一个频道，请先和我讨论名称、定位、主题和受众，整理待确认的频道提案；保存后再衔接本期创作。' },
] as const;

export type ConversationWorkflowKind = typeof CONVERSATION_WORKFLOWS[number]['kind'];

export function workflowDraft(kind: ConversationWorkflowKind, draft: string): string {
  // Replace only our generated starter when choosing another flow; keep the
  // Creator's topic/edits rather than stacking contradictory menu prompts.
  const old = CONVERSATION_WORKFLOWS.find(w => draft === w.prompt || draft.startsWith(w.prompt + '\n\n'));
  const content = old ? draft.slice(old.prompt.length).replace(/^\n\n/, '') : draft;
  const flow = CONVERSATION_WORKFLOWS.find(w => w.kind === kind)!;
  return flow.prompt + (content.trim() ? '\n\n' + content : '');
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
