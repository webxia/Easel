// Isolated UI fixture: network requests are intercepted by workspace-browser.mjs.
import React from 'react';
import { createRoot } from 'react-dom/client';
import ChatPage from '../src/components/ChatPage';
import '../src/styles/index.css';
import type { ChatSession } from '../src/lib/store';
const scenario = new URLSearchParams(location.search).get('scenario') ?? 'proposal';
const session = { id: 'fixture-chat', title: '雨后的城市', capability: 'ai-film', activeCreationId: 'fixture-creation',
  activeCreationPhase: scenario === 'proposal' ? 'proposal_ready' : 'production_confirmed',
  messages: [{ role: 'user', content: '做一支雨后城市短片，15 秒，9:16，静音，简体中文。' },
    { role: 'assistant', content: '核心表达：雨后城市的平静。用已有街景，15 秒竖屏静音，不自动发布。' }],
} as ChatSession;
createRoot(document.getElementById('root')!).render(<ChatPage session={session} onSend={() => {}} onCapabilityChange={() => {}}
  onConfirmProduction={() => {}} onStop={() => {}} onResend={() => {}} />);
