import type { ChatMessage } from './store';

/** Merge actual assistant output by durable turn identity, preserving user drafts/history. */
export function mergeTaskReplies(messages: ChatMessage[], replies: ChatMessage[]): ChatMessage[] {
  let result = messages;
  for (const reply of replies) {
    if (!reply.serverTurnId || reply.role !== 'assistant') continue;
    const index = result.findIndex(m => m.serverTurnId === reply.serverTurnId);
    const unchanged=index>=0 && ['content','resultState','deliveryError','beforeUserTurnId','beforeUserMessage','beforeUserOccurrence','publicationSource']
      .every(key=>JSON.stringify(result[index][key as keyof ChatMessage])===JSON.stringify(reply[key as keyof ChatMessage]));
    const value=unchanged?result[index]:reply;
    const without=index<0?result:result.filter((_,i)=>i!==index);
    let anchor=reply.beforeUserTurnId?without.findIndex(m=>m.role==='user' && m.userTurnId===reply.beforeUserTurnId):-1;
    if(anchor<0 && reply.beforeUserMessage){
      let occurrence=0;
      anchor=without.findIndex(m=>m.role==='user' && m.content===reply.beforeUserMessage
        && ++occurrence===(reply.beforeUserOccurrence || 1));
    }
    const at=anchor>=0?anchor:index>=0?index:without.length;
    if(index===at && unchanged)continue;
    result=[...without.slice(0,at),value,...without.slice(at)];
  }
  return result.length===messages.length && result.every((m,i)=>m===messages[i])?messages:result;
}
