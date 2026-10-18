export type Json = Record<string, unknown>;
export interface VideoSettings {
  duration_seconds: number; aspect_ratio: '9:16' | '16:9'; audio_mode: 'silent' | 'music' | 'voice' | 'mixed';
  voice?: { provider: string; model: string; voice_id: string; engine: string; parameters: Json } | null;
  subtitles?: { enabled: boolean; font: string; size: number; color: string; outline: string; background: string; position: 'top' | 'middle' | 'bottom' };
}
export interface CreativePlan {
  director_revision_id?: string | null; schema_version: number; title: string; summary: string; script: string;
  scenes: { id: string; purpose: string; visual: string; narration: string; duration_seconds?: number; required_input_ids: string[] }[];
  settings: VideoSettings; facts: string[]; core_views: string[]; constraints: string[]; adaptation_permissions: string[];
}
export interface ProductionArtifact { id: string; run_id?: string; kind: string; media_type: string; output_revision?: number; quality_state: string; manual_review_required?: boolean; export_artifact_id?: string }
export interface ProductionTask { id: string; run_id: string; kind: string; state: string; payload_json?: string; error_json?: string; result_json?: string }
export interface WorkSummary { channel_id?:string; id: string; title: string; revision: number; state: string; updated_at: string; accepted_output_id?: string }
export interface Work extends WorkSummary {
  conversation_brief?:{entries:{kind:string;text:string;source_refs:string[]}[]}; current_plan_revision?: number; pending_operations: {id:string;state:string;kind:string}[]; active_run_id?: string; profile_ref?: string; channel_id?: string; cursor: number; input_text: string; settings: Partial<VideoSettings>;
  inputs: { id: string; kind: string; usage: string; original_name: string; text_content: string }[];
  plans: { revision: number; plan_hash: string; confirmed_at?: string; plan: CreativePlan }[];
  runs: { id: string; plan_revision?: number; kind: string; state: string }[]; tasks: ProductionTask[]; artifacts: ProductionArtifact[];
  progress?: {kind:string;run_id:string;detail:{stage?:string;completed_steps?:number;total_steps?:number;completed_segments?:number;total_segments?:number}}[];
  reviews: {id:string;output_id:string;feedback:string;change_hash:string;changes:{summary?:string;reason?:string;affected?:string[];expands_scope?:boolean;requires_new_generation?:boolean}}[];
  quota: Record<string, { limit: number; used: number; unknown: number; reserved: number; available: number }>;
}
export interface Channel { id: string; name: string; revision: number; profile_ref: string; profile_name: string; archived: boolean; director_ids: string[]; default_director_revision?: string; settings: Json; creative_basis?:Record<string,string> }
export interface Director { id: string; name: string; revision: number; archived: boolean; versions: { id: string; revision: number; style_confirmed: boolean; accepted_at?: string; style: Json; evidence: Json[] }[] }
export interface ServiceChoice { provider: string; model: string; mode: string; label: string; available: boolean }

const base = window.location.pathname.replace(/\/index\.html$/, '').replace(/\/$/, '');
export const productionURL = (path: string) => `${base}/api/production/${path}`;
export async function productionRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(productionURL(path), { cache: 'no-store', ...options });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.user_message || (typeof result.detail === 'string' ? result.detail : '请求失败，请检查输入'));
  return result as T;
}
export function productionCommand<T = { work_id?: string; id?: string; revision: number }>(path: string, payload: Json, revision?: number, method = 'POST', commandId: string = crypto.randomUUID()): Promise<T> {
  return productionRequest(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ command_id: commandId, expected_revision: revision ?? null, payload }) });
}
export const artifactURL = (id: string) => productionURL(`artifacts/${encodeURIComponent(id)}/content`);
export function newerSnapshot(current: Work | null, incoming: Work, selectedId: string): Work | null {
  if (incoming.id !== selectedId || (current?.id === incoming.id && incoming.cursor < current.cursor)) return current;
  return incoming;
}
export const workLabels: Record<string, string> = {
  discussing: '讨论创作', awaiting_confirmation: '待确认方案', producing: '制作中', needs_decision: '需要你决定',
  preview_needs_fix: '待修预览', reviewable: '可审阅首版', cancelled: '已取消',
};
