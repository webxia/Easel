import type { ChatMessage } from './store';

/** Merge actual assistant output by durable turn identity, preserving user drafts/history. */
export function mergeTaskReplies(messages: ChatMessage[], replies: ChatMessage[]): ChatMessage[] {
  let result = messages;
  for (const reply of replies) {
    if (!reply.serverTurnId || reply.role !== 'assistant') continue;
    const index = result.findIndex(m => m.serverTurnId === reply.serverTurnId);
    if (index < 0) result = [...result, reply];
    else if (result[index].content !== reply.content || result[index].resultState !== reply.resultState) {
      result = result.slice(); result[index] = reply;
    }
  }
  return result;
}
