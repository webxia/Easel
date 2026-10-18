import { definePluginEntry } from 'openclaw/plugin-sdk/plugin-entry';
import { createWorkBridge } from './tools.mjs';

export default definePluginEntry({
  id: 'easel-work',
  name: 'Easel Work Bridge',
  description: 'A1 restricted work bridge; explicit installation only.',
  register: createWorkBridge,
});
