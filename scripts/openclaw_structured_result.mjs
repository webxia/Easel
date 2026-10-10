// OpenClaw compatibility support. Installed only by the reviewed patcher.
// No network, model execution or workflow ownership lives in this module.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const VERSION = 'easel-structured-result@1';
export const TOOL = 'submit_semantic_plan';
export const MAX_ARGUMENT_BYTES = 8 * 1024 * 1024;
const failure = code => { throw new Error(code); };
export const sha256 = text => crypto.createHash('sha256').update(text, 'utf8').digest('hex');

// JSON object member order does not change the schema identity.
export function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort()
    .map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
  const encoded = JSON.stringify(value);
  if (encoded === undefined || typeof value === 'number' && !Number.isFinite(value))
    failure('STRUCTURED_REQUEST_INVALID');
  return encoded;
}

const secretKey = /(?:api.?key|access.?token|\btoken\b|password|secret|credential|private.?key|authorization)/i;
const secretPatterns = [
  /\bBearer\s+[A-Za-z0-9._~+/-]{8,}={0,2}/i,
  /\b(?:sk|key|token)[-_][A-Za-z0-9_-]{12,}\b/i,
  /\b(?:[A-Z0-9_-]*(?:API[_-]?KEY|ACCESS[_-]?TOKEN|SECRET|PASSWORD|AUTHORIZATION))\s*[:=]\s*["']?[^\s,;"']+/i,
];
function safeString(value) {
  if (secretPatterns.some(pattern => pattern.test(value))) failure('STRUCTURED_STORAGE_REJECTED');
  for (let i = 0; i < value.length; i++) {
    const code = value.charCodeAt(i);
    if (code >= 0xd800 && code <= 0xdbff) {
      const low = value.charCodeAt(++i);
      if (!(low >= 0xdc00 && low <= 0xdfff)) failure('STRUCTURED_STORAGE_REJECTED');
    } else if (code >= 0xdc00 && code <= 0xdfff) failure('STRUCTURED_STORAGE_REJECTED');
  }
}

function safeStoredValue(value, key = '', depth = 0) {
  if (depth > 64) failure('STRUCTURED_STORAGE_REJECTED');
  const empty = value == null || value === '' || typeof value === 'object' &&
    Object.keys(value).length === 0;
  if (secretKey.test(key) && !empty) failure('STRUCTURED_STORAGE_REJECTED');
  if (typeof value === 'string') safeString(value);
  else if (typeof value === 'number' && !Number.isFinite(value)) failure('STRUCTURED_STORAGE_REJECTED');
  else if (value && typeof value === 'object')
    for (const [name, item] of Object.entries(value)) safeStoredValue(item, name, depth + 1);
}

// Parse members before JSON.parse can erase duplicate or escaped secret keys.
// Exceptions contain a fixed classification, never an input excerpt.
export function safeArguments(raw) {
  if (typeof raw !== 'string' || Buffer.byteLength(raw, 'utf8') > MAX_ARGUMENT_BYTES)
    failure('STRUCTURED_CAPACITY_REJECTED');
  safeString(raw);
  let position = 0;
  const whitespace = () => { while (/[\x20\t\r\n]/.test(raw[position] ?? '\0')) position++; };
  function string() {
    const start = position++;
    let escaped = false;
    while (position < raw.length) {
      const next = raw[position++];
      if (next === '"' && !escaped) {
        let value;
        try { value = JSON.parse(raw.slice(start, position)); }
        catch { failure('STRUCTURED_STORAGE_REJECTED'); }
        safeString(value);
        return value;
      }
      if (next === '\\' && !escaped) escaped = true;
      else escaped = false;
    }
    failure('STRUCTURED_STORAGE_REJECTED');
  }
  function read(depth = 0) {
    if (depth > 64) failure('STRUCTURED_STORAGE_REJECTED');
    whitespace();
    if (raw[position] === '"') return string();
    if (raw[position] === '{' || raw[position] === '[') {
      const object = raw[position++] === '{';
      const end = object ? '}' : ']';
      const value = object ? Object.create(null) : [];
      const keys = new Set();
      whitespace();
      if (raw[position] === end) { position++; return value; }
      while (position < raw.length) {
        whitespace();
        let key;
        if (object) {
          if (raw[position] !== '"') failure('STRUCTURED_STORAGE_REJECTED');
          key = string();
          if (keys.has(key)) failure('STRUCTURED_STORAGE_REJECTED');
          keys.add(key);
          whitespace();
          if (raw[position++] !== ':') failure('STRUCTURED_STORAGE_REJECTED');
        }
        const item = read(depth + 1);
        if (object) {
          const empty = item === null || item === '' || typeof item === 'object' &&
            Object.keys(item).length === 0;
          if (secretKey.test(key) && !empty) failure('STRUCTURED_STORAGE_REJECTED');
          value[key] = item;
        } else value.push(item);
        whitespace();
        const next = raw[position++];
        if (next === end) return value;
        if (next !== ',') failure('STRUCTURED_STORAGE_REJECTED');
      }
      failure('STRUCTURED_STORAGE_REJECTED');
    }
    const match = /^(?:true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/.exec(raw.slice(position));
    if (!match) failure('STRUCTURED_STORAGE_REJECTED');
    position += match[0].length;
    const value = JSON.parse(match[0]);
    if (typeof value === 'number' && !Number.isFinite(value)) failure('STRUCTURED_STORAGE_REJECTED');
    return value;
  }
  const value = read();
  whitespace();
  if (position !== raw.length || value === null || Array.isArray(value) || typeof value !== 'object')
    failure('STRUCTURED_STORAGE_REJECTED');
  return value;
}

export function validateRequest(request) {
  if (!request || request.version !== VERSION || request.name !== TOOL ||
      request.schema?.type !== 'object' ||
      Object.keys(request).sort().join(',') !== 'name,schema,schemaSha256,version' ||
      request.schemaSha256 !== sha256(canonical(request.schema)))
    failure('STRUCTURED_REQUEST_INVALID');
  return request;
}

export function validatePayload(payload, request) {
  validateRequest(request);
  const tools = payload?.tools;
  if (!Array.isArray(tools) || tools.length !== 1 || tools[0]?.type !== 'function' ||
      tools[0].function?.name !== TOOL ||
      sha256(canonical(tools[0].function.parameters)) !== request.schemaSha256 ||
      payload.tool_choice?.type !== 'function' || payload.tool_choice.function?.name !== TOOL ||
      payload.parallel_tool_calls !== false) failure('STRUCTURED_PAYLOAD_CHANGED');
}

// Persist the protocol ownership before entering an attempt. Native restart
// recovery must not drop stream options and silently execute this session as an
// ordinary agent. A malformed/partial binding is UNKNOWN, never an empty slot.
export function assertSessionProtocol(directory, identity, request) {
  if (typeof identity?.sessionId !== 'string' || !identity.sessionId) {
    if (!request) return;
    failure('STRUCTURED_IDENTITY_INVALID');
  }
  const file = path.join(directory, 'session-' + sha256(identity.sessionId) + '.json');
  if (!request && !fs.existsSync(file)) return;
  if (!request) failure('STRUCTURED_RECOVERY_REQUIRED');
  validateRequest(request);
  const expected = canonical({version: VERSION, runId: identity.runId,
    sessionId: identity.sessionId, provider: identity.provider, model: identity.model,
    schemaSha256: request.schemaSha256});
  safeArguments(expected);
  let descriptor;
  try {
    fs.mkdirSync(directory, {recursive: true, mode: 0o700});
    if (fs.lstatSync(directory).isSymbolicLink()) failure('STRUCTURED_LEDGER_UNSAFE');
    try {
      descriptor = fs.openSync(file, 'wx', 0o600);
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
      if (fs.lstatSync(file).isSymbolicLink() || fs.statSync(file).size > 16384 ||
          fs.readFileSync(file, 'utf8') !== expected) failure('STRUCTURED_RECOVERY_REQUIRED');
      return;
    }
    fs.writeFileSync(descriptor, expected);
    fs.fsyncSync(descriptor);
    fs.closeSync(descriptor);
    descriptor = undefined;
    const parent = fs.openSync(directory, 'r');
    try { fs.fsyncSync(parent); } finally { fs.closeSync(parent); }
  } catch {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    failure('STRUCTURED_RECOVERY_REQUIRED');
  }
}

export function bindAttempt(streamFn, request, identity, directory) {
  validateRequest(request);
  return (model, context, options = {}) => {
    if (model.api !== 'openai-completions' || model.provider !== identity.provider ||
        model.id !== identity.model) failure('STRUCTURED_ROUTE_CHANGED');
    return streamFn(model, context, {
      ...options,
      easelStructuredResult: {request, identity, directory},
      toolChoice: {type: 'function', function: {name: TOOL}},
      onPayload: async (value, selectedModel) => {
        const payload = await options.onPayload?.(value, selectedModel) ?? value;
        // Native normalizers may transform schemas for ordinary tools. This
        // request sends the exact Harness schema, without compatibility pruning.
        payload.tools = [{type: 'function', function: {name: TOOL,
          description: request.schema.title === 'PlanningVisualReview' ? 'Submit the complete independent review in the required question slots.' :
            request.schema.title === 'PlanningLocalRepair' ? 'Submit only the requested local repairs in the required target slots.' :
            'Submit the complete semantic plan candidate for Harness validation.',
          parameters: request.schema}}];
        payload.tool_choice = {type: 'function', function: {name: TOOL}};
        payload.parallel_tool_calls = false;
        validatePayload(payload, request);
        return payload;
      },
    });
  };
}

export function candidateEvidence(message, request) {
  validateRequest(request);
  const calls = message?.content?.filter(block => block.type === 'toolCall') ?? [];
  if (message?.easelProviderFinishReason !== 'tool_calls' || message.stopReason !== 'toolUse' ||
      calls.length !== 1 || calls[0].name !== TOOL || !calls[0].id)
    failure('STRUCTURED_TERMINAL_REJECTED');
  const call = calls[0];
  const parsed = safeArguments(call.easelRawArguments);
  if (canonical(parsed) !== canonical(call.arguments)) failure('STRUCTURED_ARGUMENTS_CHANGED');
  // Check all additional model text before any Runtime subscriber can persist it.
  safeStoredValue(message);
  return {version: VERSION, schemaSha256: request.schemaSha256, toolCallId: call.id,
    providerFinishReason: message.easelProviderFinishReason,
    rawSha256: sha256(call.easelRawArguments), rawBytes: Buffer.byteLength(call.easelRawArguments)};
}

const REJECTION_VERSION = 'easel-structured-rejection@1';
// Exact literals from the pinned SDK only. Never persist exception text or stack.
const sdkFailureMessages = new Map([
  ['Stream ended without finish_reason', 'STRUCTURED_SDK_FINISH_REASON_MISSING'],
  ['Exceeded tool-call argument buffer limit', 'STRUCTURED_SDK_ARGUMENT_BUFFER_LIMIT'],
  ['Exceeded legacy tool-call content buffer limit', 'STRUCTURED_SDK_LEGACY_CONTENT_BUFFER_LIMIT'],
  ['Exceeded post-tool-call delta buffer limit', 'STRUCTURED_SDK_POST_TOOL_BUFFER_LIMIT'],
]);
const sdkFailureTypes = new Map([
  [SyntaxError, 'STRUCTURED_SDK_SYNTAX_ERROR'],
  [TypeError, 'STRUCTURED_SDK_TYPE_ERROR'],
  [RangeError, 'STRUCTURED_SDK_RANGE_ERROR'],
]);
const rejectionCodes = new Set(['STRUCTURED_TERMINAL_REJECTED', 'STRUCTURED_STORAGE_REJECTED',
  'STRUCTURED_CAPACITY_REJECTED', 'STRUCTURED_ARGUMENTS_CHANGED', 'STRUCTURED_REQUEST_INVALID',
  'STRUCTURED_EXECUTION_FAILED', ...sdkFailureMessages.values(), ...sdkFailureTypes.values()]);
const errorCodes = new Set([...rejectionCodes, 'STRUCTURED_PAYLOAD_CHANGED',
  'STRUCTURED_ROUTE_CHANGED', 'STRUCTURED_IDENTITY_INVALID', 'STRUCTURED_LEDGER_UNSAFE',
  'STRUCTURED_SUBMISSION_UNCERTAIN', 'STRUCTURED_RECOVERY_REQUIRED',
  'STRUCTURED_EVENT_AFTER_TERMINAL']);
const shapes = new Set(['missing', 'undefined', 'null', 'array', 'object', 'string',
  'number', 'boolean', 'other']);
const providerEnds = new Set(['tool_calls', 'function_call', 'stop', 'length', 'content_filter']);
const nativeEnds = new Set(['toolUse', 'stop', 'length', 'error', 'aborted']);
const unavailableEnds = ['MISSING', 'NULL', 'UNKNOWN'];
const shape = value => value === null ? 'null' : Array.isArray(value) ? 'array' :
  shapes.has(typeof value) ? typeof value : 'other';
const memberShape = (value, key) => value != null && Object.hasOwn(value, key)
  ? shape(value[key]) : 'missing';
function terminalValue(message, key, allowed) {
  const kind = memberShape(message, key);
  return kind === 'missing' ? 'MISSING' : kind === 'null' ? 'NULL' :
    allowed.has(message[key]) ? message[key] : 'UNKNOWN';
}

function rejectionRecord(scope, message, category) {
  const calls = Array.isArray(message?.content)
    ? message.content.filter(block => block?.type === 'toolCall') : null;
  const call = calls?.length === 1 ? calls[0] : undefined;
  return {version: REJECTION_VERSION, ...Object.fromEntries(
    ['runId', 'sessionId', 'provider', 'model'].map(key => [key, scope.identity[key]])),
    schemaSha256: scope.request.schemaSha256,
    category: rejectionCodes.has(category) ? category : 'STRUCTURED_EXECUTION_FAILED',
    messageShape: shape(message), contentShape: memberShape(message, 'content'),
    providerFinishShape: memberShape(message, 'easelProviderFinishReason'),
    providerFinishValue: terminalValue(message, 'easelProviderFinishReason', providerEnds),
    nativeStopShape: memberShape(message, 'stopReason'),
    nativeStopValue: terminalValue(message, 'stopReason', nativeEnds),
    toolCallCount: calls?.length ?? null, uniqueExpectedTool: call?.name === TOOL,
    idPresent: Boolean(call?.id), idShape: memberShape(call, 'id'),
    rawArgumentsShape: memberShape(call, 'easelRawArguments'),
    rawArgumentBytes: typeof call?.easelRawArguments === 'string'
      ? Buffer.byteLength(call.easelRawArguments, 'utf8') : null};
}

function existingRejection(file, expected) {
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o077) || stat.size > 16384)
    return false;
  const value = safeArguments(fs.readFileSync(file, 'utf8'));
  if (Object.keys(value).sort().join(',') !== Object.keys(expected).sort().join(',')) return false;
  for (const key of ['version', 'runId', 'sessionId', 'provider', 'model', 'schemaSha256'])
    if (value[key] !== expected[key]) return false;
  if (!rejectionCodes.has(value.category)) return false;
  for (const key of ['messageShape', 'contentShape', 'providerFinishShape', 'nativeStopShape',
    'idShape', 'rawArgumentsShape']) if (!shapes.has(value[key])) return false;
  if (![...providerEnds, ...unavailableEnds].includes(value.providerFinishValue) ||
      ![...nativeEnds, ...unavailableEnds].includes(value.nativeStopValue)) return false;
  for (const key of ['toolCallCount', 'rawArgumentBytes'])
    if (value[key] !== null && (!Number.isSafeInteger(value[key]) || value[key] < 0)) return false;
  return typeof value.uniqueExpectedTool === 'boolean' && typeof value.idPresent === 'boolean';
}

// This is diagnostic metadata, never a candidate or a replacement for RESERVED.
// Only a complete fsynced private file is published; later errors cannot replace it.
export function retainRejection(scope, message, category) {
  let temporary;
  let descriptor;
  try {
    validateRequest(scope.request);
    if (!path.isAbsolute(scope.directory)) return 'UNAVAILABLE';
    const parent = fs.lstatSync(scope.directory);
    if (!parent.isDirectory() || parent.isSymbolicLink() || (parent.mode & 0o077)) return 'UNAVAILABLE';
    const record = rejectionRecord(scope, message, category);
    const bytes = canonical(record);
    safeArguments(bytes);
    const key = sha256(canonical({runId: record.runId, sessionId: record.sessionId}));
    const file = path.join(scope.directory, 'rejection-' + key + '.json');
    if (fs.existsSync(file)) return existingRejection(file, record) ? 'RETAINED' : 'UNAVAILABLE';
    temporary = path.join(scope.directory, '.rejection-' + crypto.randomUUID() + '.tmp');
    descriptor = fs.openSync(temporary, 'wx', 0o600);
    fs.writeFileSync(descriptor, bytes);
    fs.fsyncSync(descriptor);
    fs.closeSync(descriptor);
    descriptor = undefined;
    try { fs.linkSync(temporary, file); }
    catch (error) {
      if (error.code !== 'EEXIST') throw error;
      return existingRejection(file, record) ? 'RETAINED' : 'UNAVAILABLE';
    }
    const directory = fs.openSync(scope.directory, 'r');
    try { fs.fsyncSync(directory); } finally { fs.closeSync(directory); }
    return 'SAVED';
  } catch {
    // Keep the original rejection; absence/invalidity is diagnostic unavailability.
    return 'UNAVAILABLE';
  } finally {
    if (descriptor !== undefined) {
      try { fs.closeSync(descriptor); } catch { /* Diagnostics cannot mask the original rejection. */ }
    }
    if (temporary) {
      try { fs.unlinkSync(temporary); } catch { /* Never overwrite a prior rejection. */ }
    }
  }
}

// The transport calls this before its native cleanup removes unfinished tools.
// Diagnostic failures never replace the SDK error or authorize another submission.
export function retainExecutionFailure(scope, message, error) {
  try {
    let category = errorCodes.has(error?.message) ? error.message : sdkFailureMessages.get(error?.message);
    if (!category) {
      for (const [Type, code] of sdkFailureTypes) {
        if (error instanceof Type) { category = code; break; }
      }
    }
    return retainRejection(scope, message, category ?? 'STRUCTURED_EXECUTION_FAILED');
  } catch {
    return 'UNAVAILABLE';
  }
}

// Hold partial events inside the provider transport. They must not reach
// transcript/raw-stream/diagnostic subscribers before complete storage checking.
export function protectedStream(destination, scope) {
  let ended = false;
  let terminal;
  return {
    push(event) {
      if (ended) failure('STRUCTURED_EVENT_AFTER_TERMINAL');
      if (event.type !== 'done' && event.type !== 'error') return;
      if (event.type === 'done') {
        let evidence;
        try { evidence = candidateEvidence(event.message, scope.request); }
        catch (error) {
          retainRejection(scope, event.message, error?.message);
          throw error;
        }
        ended = true;
        event.message.easelStructuredResult = evidence;
        terminal = event.message;
        destination.push({type: 'start', partial: {...event.message, content: []}});
        for (const [contentIndex, block] of event.message.content.entries()) {
          if (block.type !== 'toolCall') continue;
          destination.push({type: 'toolcall_start', contentIndex, partial: event.message});
          destination.push({type: 'toolcall_end', contentIndex, toolCall: block, partial: event.message});
        }
        destination.push(event);
      } else {
        ended = true;
        const source = event.error;
        const category = errorCodes.has(source?.errorMessage)
          ? source.errorMessage : 'STRUCTURED_EXECUTION_FAILED';
        retainRejection(scope, source, category);
        terminal = {role: 'assistant', content: [], api: 'openai-completions',
          provider: scope.identity.provider, model: scope.identity.model,
          timestamp: Date.now(), usage: source?.usage,
          stopReason: source?.stopReason === 'aborted' ? 'aborted' : 'error',
          errorMessage: category};
        destination.push({type: 'error', reason: terminal.stopReason, error: terminal});
      }
    },
    end() { destination.end(terminal); },
  };
}

// Call at the last fetch boundary for every attempt, including framework retries.
// Exclusive durable creation is intentionally never undone after any failure.
export function reserveSubmission(directory, identity, payload, request) {
  validatePayload(payload, request);
  if (!path.isAbsolute(directory) || !identity ||
      ['runId', 'sessionId', 'provider', 'model'].some(key =>
        typeof identity[key] !== 'string' || !identity[key])) failure('STRUCTURED_IDENTITY_INVALID');
  // Filename is based on original run/session, not mutable schema or model.
  const key = sha256(canonical({runId: identity.runId, sessionId: identity.sessionId}));
  const record = {version: VERSION, state: 'RESERVED',
    runId: identity.runId, sessionId: identity.sessionId,
    provider: identity.provider, model: identity.model,
    schemaSha256: request.schemaSha256};
  // Metadata only. Never write prompt, candidate or credentials to the guard.
  safeArguments(canonical(record));
  let descriptor;
  try {
    fs.mkdirSync(directory, {recursive: true, mode: 0o700});
    if (fs.lstatSync(directory).isSymbolicLink()) failure('STRUCTURED_LEDGER_UNSAFE');
    descriptor = fs.openSync(path.join(directory, key + '.json'), 'wx', 0o600);
    fs.writeFileSync(descriptor, canonical(record));
    fs.fsyncSync(descriptor);
    fs.closeSync(descriptor);
    descriptor = undefined;
    const parent = fs.openSync(directory, 'r');
    try { fs.fsyncSync(parent); } finally { fs.closeSync(parent); }
  } catch {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    failure('STRUCTURED_SUBMISSION_UNCERTAIN');
  }
  return record;
}
