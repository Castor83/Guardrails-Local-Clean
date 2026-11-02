// Narrow OpenCode v2.1.4 Promise-plugin adapter. No packages, filesystem writes,
// model calls or independent HTTP client. The V1 engine is only a local checker.
// Its parentID/parts are DERIVED INTERNAL COMPATIBILITY ENVELOPES, never claimed
// to exist in the V2 SDK: durable true-user ID -> guarded Request -> emitted call
// -> identical native before/after lifecycle. V2 has no native parentID.
import { createHash, randomUUID } from 'node:crypto';
import path from 'node:path';
import evidenceEngine from '../guardrails-evidence.mjs';

const MAX_BYTES = 1_048_576, MAX_WAIT = 60_000;
const isID = value => typeof value === 'string' && /^[\w-]{1,160}$/.test(value);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
function bounded(map, max) { while (map.size > max) map.delete(map.keys().next().value); }
function fingerprint(value) {
  let bytes = 0;
  function canonical(v, depth = 0) {
    if (depth > 20) throw Error('depth');
    if (v === null || ['string', 'number', 'boolean'].includes(typeof v)) {
      const text = JSON.stringify(v); bytes += Buffer.byteLength(text);
      if (bytes > MAX_BYTES) throw Error('size'); return text;
    }
    if (Array.isArray(v)) return `[${v.map(x => canonical(x, depth + 1)).join(',')}]`;
    if (object(v)) return `{${Object.keys(v).sort().map(k => `${canonical(k, depth + 1)}:${canonical(v[k], depth + 1)}`).join(',')}}`;
    throw Error('unsupported');
  }
  try { return createHash('sha256').update(canonical(value)).digest('hex'); } catch { return null; }
}
function absolute(value) {
  if (typeof value !== 'string' || /[\0\r\n]/.test(value)) return null;
  if (/^[A-Za-z]:[\\/]/.test(value)) return path.win32.normalize(value).replaceAll('\\', '/').toLowerCase();
  return value.startsWith('/') ? path.posix.normalize(value) : null;
}
function endpoint(value) {
  try {
    // Explicit numeric loopback only; URL's alternate integer/IP spellings and
    // DNS names are intentionally outside this adapter's protocol boundary.
    if (typeof value !== 'string' || !/^http:\/\/(?:127(?:\.\d{1,3}){3}|\[::1\])(?::\d+)?\//.test(value)) return null;
    const url = new URL(value);
    if (url.protocol !== 'http:' || url.username || url.password || url.search || url.hash ||
      !url.pathname.endsWith('/v1/chat/completions')) return null;
    return url.href;
  } catch { return null; }
}
function guardError() {
  // Explicit HTTP error, not a synthetic successful model completion. No input,
  // body excerpt, tool call or exception string is released on this path.
  return new Response(JSON.stringify({ error: { type: 'guardrails_unverified',
    message: 'Guardrails UNVERIFIED: Modellantwort konnte innerhalb des begrenzten lokalen Protokolls nicht geprüft werden.' } }),
  { status: 422, headers: { 'content-type': 'application/json', 'x-guardrails-status': 'unverified' } });
}
async function readBounded(body, signal, maxBytes, timeoutMs) {
  if (!body) throw Error('missing-body');
  const reader = body.getReader(); let timer, abort, rejectBound;
  const boundary = new Promise((_resolve, reject) => { rejectBound = reject; });
  const cancel = () => { try { void reader.cancel().catch(() => {}); } catch {} };
  try {
    abort = () => { cancel(); rejectBound(Error('aborted')); };
    if (signal?.aborted) { cancel(); throw Error('aborted'); }
    signal?.addEventListener('abort', abort, { once: true });
    timer = setTimeout(() => { cancel(); rejectBound(Error('timeout')); }, timeoutMs);
    const parts = []; let size = 0;
    while (true) {
      const chunk = await Promise.race([reader.read(), boundary]);
      if (signal?.aborted) throw Error('aborted');
      if (chunk.done) break;
      if (!(chunk.value instanceof Uint8Array)) throw Error('nonbytes');
      size += chunk.value.byteLength;
      if (size > maxBytes) { cancel(); throw Error('size'); }
      parts.push(chunk.value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const p of parts) { bytes.set(p, offset); offset += p.length; }
    return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  } catch (error) { cancel(); throw error; }
  finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); try { reader.releaseLock(); } catch {} }
}

// Parse only one-choice OpenAI Chat Completions (JSON or SSE), including refusal.
// Reasoning, usage, finish_reason and function-tool frames stay in their objects.
function parseResponse(text, stream) {
  const frames = [], slots = [], tools = new Map(); let finished = false;
  function addSlot(parent, key) {
    if (parent[key] !== undefined && parent[key] !== null && typeof parent[key] !== 'string') throw Error('text-shape');
    if (typeof parent[key] === 'string') slots.push({ parent, key, text: parent[key] });
  }
  function addTool(call, streaming) {
    if (!object(call) || (call.type !== undefined && call.type !== 'function') || !object(call.function)) throw Error('tool-shape');
    const index = streaming ? call.index : tools.size;
    if (!Number.isSafeInteger(index) || index < 0 || index >= 128) throw Error('tool-index');
    let t = tools.get(index);
    if (!t) { t = { id: '', name: '', args: '' }; tools.set(index, t); }
    if (call.id !== undefined) {
      if (!isID(call.id) || (t.id && t.id !== call.id)) throw Error('tool-id'); t.id = call.id;
    }
    for (const [from, to] of [['name', 'name'], ['arguments', 'args']]) if (call.function[from] !== undefined) {
      if (typeof call.function[from] !== 'string') throw Error('tool-field'); t[to] += call.function[from];
    }
  }
  function choice(c, streaming) {
    if (!object(c) || c.index !== 0) throw Error('choice');
    const message = streaming ? c.delta : c.message;
    if (!object(message) || (message.role !== undefined && message.role !== 'assistant') ||
      message.function_call !== undefined || message.audio !== undefined) throw Error('message');
    addSlot(message, 'content'); addSlot(message, 'refusal');
    if (message.tool_calls !== undefined) {
      if (!Array.isArray(message.tool_calls)) throw Error('tools');
      for (const call of message.tool_calls) addTool(call, streaming);
    }
    if (c.finish_reason !== undefined && c.finish_reason !== null) {
      if (typeof c.finish_reason !== 'string' || finished) throw Error('finish'); finished = true;
    }
  }
  function frame(value, streaming) {
    if (!object(value) || value.error !== undefined || value.object !== (streaming ? 'chat.completion.chunk' : 'chat.completion') ||
      !Array.isArray(value.choices) || value.choices.length > 1) throw Error('protocol');
    if (value.choices.length === 0) { if (!streaming || !object(value.usage)) throw Error('usage'); }
    else { if (finished) throw Error('after-finish'); choice(value.choices[0], streaming); }
    frames.push(value);
  }
  if (!stream) frame(JSON.parse(text), false);
  else {
    let done = false;
    for (const block of text.replaceAll('\r\n', '\n').split('\n\n')) {
      if (!block.trim()) continue;
      const lines = block.split('\n'); const data = [];
      for (const line of lines) {
        if (!line || line.startsWith(':')) continue;
        if (!line.startsWith('data:')) throw Error('sse-field');
        data.push(line.slice(5).replace(/^ /, ''));
      }
      if (!data.length) continue;
      if (done) throw Error('after-done');
      const value = data.join('\n');
      if (value === '[DONE]') { done = true; continue; }
      frame(JSON.parse(value), true);
    }
    if (!done) throw Error('missing-done');
  }
  if (!finished || !frames.length) throw Error('incomplete');
  const calls = []; const seen = new Set();
  for (const t of tools.values()) {
    if (!isID(t.id) || !isID(t.name) || seen.has(t.id)) throw Error('call-identity');
    const input = JSON.parse(t.args); if (!object(input) || !fingerprint(input)) throw Error('call-input');
    seen.add(t.id); calls.push({ id: t.id, tool: t.name, hash: fingerprint(input) });
  }
  // A complete envelope alone is not an answer. Reasoning and older receipts
  // cannot fill an empty final response; valid text-free tool calls may continue.
  if (!calls.length && !slots.some(slot => slot.text.trim().length > 0)) throw Error('empty-completion');
  return { slots, calls, text: slots.map(s => s.text).join(''), serialize() {
    return stream ? frames.map(f => `data: ${JSON.stringify(f)}\n\n`).join('') + 'data: [DONE]\n\n' : JSON.stringify(frames[0]);
  } };
}

function nativeResult(event) {
  const result = event.result, out = result?.output, meta = result?.metadata;
  const failed = event.status !== 'completed' || !object(result) || result.isError === true ||
    result.error || meta?.error || out?.isError === true;
  if (event.tool === 'shell') {
    const invalid = failed || !object(out) || typeof out.output !== 'string' || out.truncated !== false ||
      out.timeout === true || Boolean(out.signal) || (out.status !== undefined && out.status !== 'completed') ||
      meta?.timeout === true || meta?.truncated === true || Boolean(meta?.signal) || meta?.status === 'running' ||
      (meta?.exit !== undefined && meta.exit !== out.exit);
    return { tool: 'bash', args: event.input,
      output: { output: typeof out?.output === 'string' ? out.output : '',
        metadata: { exit: invalid || typeof out.exit !== 'number' ? null : out.exit, error: Boolean(invalid) } } };
  }
  if (event.tool === 'write') {
    const contents = typeof result?.content === 'string' ? result.content :
      Array.isArray(result?.content) ? result.content.filter(p => p?.type === 'text').map(p => p.text).join('\n') : '';
    const okay = !failed && out?.operation === 'write' && typeof out.existed === 'boolean' &&
      typeof out.resource === 'string' && absolute(out.target) && absolute(out.target) === absolute(event.input?.path) &&
      (contents === `Wrote file successfully: ${out.resource}` || contents === `Created file successfully: ${out.resource}`);
    return { tool: 'write', args: { filePath: event.input?.path ?? null },
      output: { output: okay ? 'Wrote file successfully.' : '', metadata: { error: !okay } } };
  }
  // No speculative conversion of V2 edit/search/custom/MCP result formats.
  return { tool: `unsupported_${event.tool}`, args: event.input,
    output: { output: '', metadata: { error: true } } };
}
function annotate(result, annotation) {
  if (!annotation || !object(result)) return;
  if (typeof result.content === 'string') result.content += annotation;
  else if (Array.isArray(result.content)) result.content = [...result.content, { type: 'text', text: annotation.trim() }];
  else result.content = [{ type: 'text', text: annotation.trim() }];
}

// Plugin.define is an identity helper in V2. A structural default Plugin export
// keeps this standalone module free of an @opencode/plugin runtime dependency.
export default {
  id: 'guardrails.local.evidence',
  async setup(ctx) {
    const configuredEndpoint = endpoint(ctx.options?.endpoint);
    const maxBytes = Number.isSafeInteger(ctx.options?.maxBytes) && ctx.options.maxBytes > 0 ? Math.min(MAX_BYTES, ctx.options.maxBytes) : MAX_BYTES;
    const timeoutMs = Number.isSafeInteger(ctx.options?.timeoutMs) && ctx.options.timeoutMs > 0 ? Math.min(MAX_WAIT, ctx.options.timeoutMs) : MAX_WAIT;
    const sessions = new Map(), requests = new WeakMap(), failedScopes = new Set(); const registrations = [];
    let denyAllOllamaRetries = false;
    function state(sid) {
      if (!isID(sid)) return null;
      if (!sessions.has(sid)) { sessions.set(sid, { envelopes: new Map(), contexts: new Map(), calls: new Map(),
        receiptRefs: new Map(), unknownEpoch: 0, engineLock: Promise.resolve() }); bounded(sessions, 32); }
      return sessions.get(sid);
    }
    const scopeKey = e => JSON.stringify([e.agent, e.model?.providerID, e.model?.id]);
    const retryKey = e => JSON.stringify([e.sessionID, e.agent, e.model?.providerID, e.model?.id]);
    const eligible = e => e.kind === 'primary' && e.model?.providerID === 'ollama';
    const engine = await evidenceEngine({ client: { session: {
      messages: async ({ path: p }) => ({ data: [...(sessions.get(p.id)?.envelopes.values() ?? [])] }),
      message: async ({ path: p }) => ({ data: sessions.get(p.id)?.envelopes.get(p.messageID) }),
    } } });
    function envelope(s, sid, user) {
      const msg = { info: { id: `gl_${randomUUID()}`, sessionID: sid, role: 'assistant', parentID: user }, parts: [] };
      s.envelopes.set(msg.info.id, msg); bounded(s.envelopes, 64); return msg;
    }
    function serialized(s, operation) {
      const next = s.engineLock.then(operation);
      s.engineLock = next.catch(() => {}); return next;
    }
    function invalidateUnknown(s) {
      if (!s) return;
      // Unknown native actions can mutate files even though they cannot earn a
      // receipt. Fence existing and overlapping receipts without inventing a
      // tool success or leaving a fake pending call in the reused V1 engine.
      s.unknownEpoch++; s.receiptRefs.clear();
    }
    registrations.push(await ctx.session.hook('context', async e => {
      if (e.model?.providerID !== 'ollama') return;
      const s = state(e.sessionID); if (!s) return;
      const output = { system: [] }; await engine['experimental.chat.system.transform']({}, output);
      // The V1 instructions' last-streaming sentence does not describe this V2
      // route: replace that sentence with the precise local HTTP route limit.
      e.system.push({ type: 'text', text: output.system[0].replace(/Der Hook prüft fertige Textteile[^\n]*/, '') +
        '\nV2: Nur die ausdrücklich eingerichtete lokale Ollama-Chat-Completions-HTTP-Route wird vor dem Parser geprüft. Andere Protokolle und spätere Pluginänderungen sind nicht abgedeckt.' });
      const key = scopeKey(e); const queue = s.contexts.get(key) ?? [];
      const binding = { user: null, key, sessionID: e.sessionID, agent: e.agent };
      queue.push(binding); s.contexts.set(key, queue); bounded(s.contexts, 32);
      if (queue.length > 16) { queue.splice(0, queue.length, null, null); return; }
      const modelUsers = Array.isArray(e.messages) ? e.messages.filter(m => m?.role === 'user').map(m => m.id) : [];
      try {
        // Promise SDK unwraps the HTTP {data} response, including in-process plugins.
        const messages = await ctx.session.context({ sessionID: e.sessionID });
        if (!Array.isArray(messages) || messages.length > 4096) return;
        for (const candidate of modelUsers.toReversed()) {
          if (!isID(candidate)) break;
          const rows = messages.filter(m => m?.id === candidate);
          if (rows.length !== 1) break;
          if (rows[0].type === 'user') { binding.user = candidate; break; }
          // Only an explicitly identified synthetic contribution may be skipped.
          // A missing/new/ambiguous identity must not inherit an older task.
          if (!['synthetic', 'skill', 'shell', 'compaction', 'checkpoint'].includes(rows[0].type)) break;
        }
        if (binding.user) await engine['chat.message']({ sessionID: e.sessionID },
          { message: { role: 'user', sessionID: e.sessionID, id: binding.user } });
      } catch { /* A missing durable user never inherits session's newest task. */ }
    }, { providerID: 'ollama' }));
    registrations.push(await ctx.session.hook('http.request', async e => {
      if (!eligible(e) || !(e.request instanceof Request)) return;
      const s = state(e.sessionID), key = scopeKey(e); const queue = s?.contexts.get(key) ?? [];
      s?.contexts.delete(key);
      const binding = queue.length === 1 && queue[0] ? { ...queue[0] } : null;
      const record = { binding, key, valid: false, stream: false };
      requests.set(e.request, record);
      try {
        if (!s || !configuredEndpoint || endpoint(e.request.url) !== configuredEndpoint || e.request.method !== 'POST' || !binding) return;
        if (!/^application\/json(?:;|$)/i.test(e.request.headers.get('content-type') ?? '')) return;
        const body = JSON.parse(await readBounded(e.request.clone().body, e.request.signal, maxBytes, timeoutMs));
        if (!object(body) || typeof body.stream !== 'boolean' || !Array.isArray(body.messages)) return;
        record.stream = body.stream; record.valid = true;
      } catch { /* Unsupported/aborted request is rejected at its response boundary. */ }
    }, { providerID: 'ollama' }));
    registrations.push(await ctx.session.hook('http.response', async e => {
      if (!eligible(e)) return;
      const record = requests.get(e.request); requests.delete(e.request);
      try {
        if (!record?.valid || record.key !== scopeKey(e) || record.binding.sessionID !== e.sessionID ||
          !e.response.ok || !e.response.body) throw Error('correlation');
        const type = e.response.headers.get('content-type') ?? '';
        if (!(record.stream ? /^text\/event-stream(?:;|$)/i : /^application\/json(?:;|$)/i).test(type)) throw Error('content-type');
        const raw = await readBounded(e.response.body, e.request.signal, maxBytes, timeoutMs);
        const parsed = parseResponse(raw, record.stream), s = sessions.get(e.sessionID);
        if (!s) throw Error('state-evicted');
        const msg = envelope(s, e.sessionID, record.binding.user);
        const checkedEpoch = s.unknownEpoch;
        const checkText = parsed.text.replace(/\[GL:[a-f0-9-]{36}\]/g,
          ref => s.receiptRefs.has(ref) ? ref : '[GL:invalidated]');
        const text = { text: checkText };
        await engine['experimental.text.complete']({ sessionID: e.sessionID, messageID: msg.info.id, partID: 'gl_http' }, text);
        if (s.unknownEpoch !== checkedEpoch) throw Error('native-action-during-check');
        if (text.text === checkText) text.text = parsed.text; // Preserve honest references/quotes verbatim.
        if (e.request.signal.aborted) throw Error('aborted');
        if (text.text !== parsed.text && parsed.slots.length) {
          parsed.slots[0].parent[parsed.slots[0].key] = text.text;
          for (const slot of parsed.slots.slice(1)) slot.parent[slot.key] = '';
        }
        for (const c of parsed.calls) {
          const previous = s.calls.get(c.id);
          if (previous) { previous.invalid = true; continue; }
          s.calls.set(c.id, { ...c, user: record.binding.user, agent: record.binding.agent, before: null, settled: false });
          bounded(s.calls, 128);
        }
        const headers = new Headers(e.response.headers);
        for (const name of ['content-length', 'content-encoding', 'transfer-encoding', 'etag']) headers.delete(name);
        headers.set('x-guardrails-status', 'checked-bounded');
        e.response = new Response(parsed.serialize(), { status: e.response.status, statusText: e.response.statusText, headers });
      } catch {
        try { void e.response?.body?.cancel().catch(() => {}); } catch {}
        // V2 can otherwise make its own inference retry after a transport error.
        // Retry events have no Request ID/kind; conservatively retain this exact
        // session/agent/model scope until plugin disposal. At the finite bound,
        // stop Ollama retries broadly rather than forget a failed guard scope.
        if (failedScopes.size >= 128) { denyAllOllamaRetries = true; failedScopes.clear(); }
        else failedScopes.add(retryKey(e));
        e.response = guardError();
      }
    }, { providerID: 'ollama' }));
    registrations.push(await ctx.session.hook('retry', async e => {
      if (e.model?.providerID === 'ollama' && (denyAllOllamaRetries || failedScopes.has(retryKey(e)))) e.decision = { retry: false };
    }, { providerID: 'ollama' }));
    registrations.push(await ctx.tool.hook('execute.before', async e => {
      const s = sessions.get(e.sessionID), c = s?.calls.get(e.id);
      if (!c || c.invalid || c.settled || c.before || c.tool !== e.tool || c.agent !== e.agent ||
        !isID(e.messageID) || !c.hash || c.hash !== fingerprint(e.input)) {
        if (c) c.invalid = true; invalidateUnknown(s); return;
      }
      const normalized = nativeResult({ ...e, status: 'error' });
      c.before = { messageID: e.messageID, hash: c.hash, normalizedTool: normalized.tool, normalizedArgs: normalized.args };
      c.unknownEpoch = s.unknownEpoch;
      const msg = envelope(s, e.sessionID, c.user); c.envelope = msg;
      msg.parts.push({ type: 'tool', sessionID: e.sessionID, messageID: msg.info.id, callID: e.id,
        tool: normalized.tool, state: { input: normalized.args } });
      // The V1 checker has an active-user staging field. Keep staging+reserve
      // atomic with respect to other native before callbacks in this session.
      await serialized(s, async () => {
        await engine['chat.params']({ sessionID: e.sessionID, message: { role: 'user', sessionID: e.sessionID, id: c.user } });
        await engine['tool.execute.before']({ sessionID: e.sessionID, callID: e.id, tool: normalized.tool }, { args: normalized.args });
      });
    }));
    registrations.push(await ctx.tool.hook('execute.after', async e => {
      const s = sessions.get(e.sessionID), c = s?.calls.get(e.id);
      if (!c || c.invalid || c.settled || !c.before || c.tool !== e.tool || c.agent !== e.agent ||
        c.before.messageID !== e.messageID || c.hash !== fingerprint(e.input)) {
        if (c) c.invalid = true; invalidateUnknown(s); return;
      }
      c.settled = true;
      const normalized = nativeResult(e);
      await engine['tool.execute.after']({ sessionID: e.sessionID, callID: e.id, tool: normalized.tool, args: normalized.args }, normalized.output);
      const annotation = normalized.output.output.match(/\n\[GL:[^\n]+$/)?.[0];
      const ref = annotation?.match(/\[GL:[a-f0-9-]{36}\]/)?.[0];
      if (ref && c.unknownEpoch === s.unknownEpoch) {
        s.receiptRefs.set(ref, true); bounded(s.receiptRefs, 128);
      }
      if (e.status === 'completed') annotate(e.result, annotation);
      // Retain only identities/digests: no emitted args, full outputs or prompts.
      c.before = { messageID: e.messageID }; c.envelope.parts = []; delete c.envelope;
    }));
    return async () => { for (const r of registrations.reverse()) await r.dispose(); sessions.clear(); failedScopes.clear(); };
  },
};
