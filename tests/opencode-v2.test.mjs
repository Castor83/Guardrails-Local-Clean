import test from 'node:test';
import assert from 'node:assert/strict';

const ENDPOINT = 'http://127.0.0.1:11434/v1/chat/completions';
const MODEL = { providerID: 'ollama', id: 'fixture-model' };
const SUMMARY = '# tests 2\n# pass 2\n# fail 0\n# cancelled 0\n# skipped 0';

async function setup(options = {}) {
  let plugin;
  try { plugin = (await import('../tools/opencode/v2/index.mjs')).default; }
  catch (error) { if (error.code === 'ERR_MODULE_NOT_FOUND') assert.fail('V2 evidence adapter missing'); throw error; }
  const sessionHooks = new Map(), toolHooks = new Map();
  const durable = [{ type: 'user', id: 'msg_user_a', text: 'Run the focused check.' }];
  const ctx = { options: { endpoint: ENDPOINT, ...options }, session: {
    hook: async (name, callback) => { sessionHooks.set(name, callback); return { dispose: async () => {} }; },
    // V2 Promise SDK removes the HTTP {data} envelope before returning.
    context: async () => durable,
  }, tool: { hook: async (name, callback) => { toolHooks.set(name, callback); return { dispose: async () => {} }; } } };
  await plugin.setup(ctx);
  const scope = { sessionID: 'ses_a', agent: 'build', model: MODEL, kind: 'primary' };
  async function context({ user = 'msg_user_a', messages, ...override } = {}) {
    const event = { ...scope, system: [{ type: 'text', text: 'Existing system rule' }],
      messages: messages ?? [{ role: 'user', id: user, content: [{ type: 'text', text: 'Run the focused check.' }] }],
      options: {}, tools: {}, ...override };
    await sessionHooks.get('context')(event);
    return event;
  }
  async function request({ user = 'msg_user_a', stream = false, contextFirst = true, url = ENDPOINT,
    signal, ...override } = {}) {
    if (contextFirst) await context({ user, ...override });
    const request = new Request(url, { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ model: 'fixture-model', stream, messages: [{ role: 'user', content: 'fixture' }] }), signal });
    const event = { ...scope, ...override, request };
    await sessionHooks.get('http.request')(event);
    return event;
  }
  async function response(req, body, contentType = 'application/json', responseOptions = {}) {
    const event = { ...req, response: body instanceof Response ? body : new Response(body, {
      headers: { 'content-type': contentType, ...responseOptions.headers }, ...responseOptions }) };
    await sessionHooks.get('http.response')(event);
    return event.response;
  }
  async function json(text, { req, refusal, tool_calls, ...extra } = {}) {
    req ??= await request();
    return response(req, JSON.stringify({ id: 'chatcmpl_fixture', object: 'chat.completion',
      choices: [{ index: 0, message: { role: 'assistant', content: text, ...(refusal === undefined ? {} : { refusal }),
        ...(tool_calls ? { tool_calls } : {}) }, finish_reason: tool_calls ? 'tool_calls' : 'stop' }], ...extra }));
  }
  async function call({ id = 'call_a', tool = 'shell', args = { command: 'node --test tests/example.test.mjs' },
    result = { output: { output: SUMMARY, exit: 0, truncated: false }, content: [{ type: 'text', text: SUMMARY }], metadata: { exit: 0 } }, req, emit = true, before = true,
    beforeOverrides = {}, afterOverrides = {}, status = 'completed' } = {}) {
    if (emit) {
      const r = await json(null, { req, tool_calls: [{ id, type: 'function',
        function: { name: tool, arguments: JSON.stringify(args) } }] });
      assert.equal(r.status, 200, await r.text());
    }
    const event = { sessionID: 'ses_a', agent: 'build', messageID: 'msg_assistant_a', id, tool, input: args };
    if (before) await toolHooks.get('execute.before')({ ...event, ...beforeOverrides });
    const after = { ...event, status, ...(status === 'completed' ? { result: structuredClone(result) } :
      { error: { message: 'tool failed' } }), ...afterOverrides };
    await toolHooks.get('execute.after')(after);
    const text = JSON.stringify(after.result ?? {});
    return text.match(/\[GL:[a-f0-9-]+\]/)?.[0] ?? '[GL:missing]';
  }
  return { plugin, ctx, durable, scope, sessionHooks, toolHooks, context, request, response, json, call };
}
async function visible(response) {
  const body = await response.json();
  return body.choices?.[0]?.message?.content ?? body.error?.message ?? '';
}
const frame = (delta, extra = {}) => ({ id: 'chatcmpl_fixture', object: 'chat.completion.chunk',
  choices: [{ index: 0, delta, finish_reason: null }], ...extra });
const sse = frames => frames.map(x => `data: ${typeof x === 'string' ? x : JSON.stringify(x)}\n\n`).join('');

test('V2 preserves previous system rules and adds bounded evidence instructions', async () => {
  const h = await setup(); const e = await h.context();
  assert.equal(e.system[0].text, 'Existing system rule');
  assert.match(e.system.at(-1).text, /GL:ID/);
});
test('V2 buffers and marks fabricated test success before response is read', async () => {
  const h = await setup(); assert.match(await visible(await h.json('Alle Tests bestanden.')), /UNVERIFIED/);
});
test('V2 exact emitted call and native lifecycle support a scoped genuine success', async () => {
  const h = await setup(); const ref = await h.call(); assert.notEqual(ref, '[GL:missing]');
  assert.equal(await visible(await h.json(`2 Tests bestanden. ${ref}`)), `2 Tests bestanden. ${ref}`);
});

test('V2 direct Promise context array binds an actual failed test as tests, not unknown', async () => {
  const h = await setup();
  const summary = '# tests 1\n# pass 0\n# fail 1\nnot ok 1 - deliberate failure';
  const result = { output: { output: summary, exit: 1, truncated: false },
    content: [{ type: 'text', text: summary }], metadata: { exit: 1 } };
  const ref = await h.call({ args: { command: 'node --test --test-reporter=tap fail.test.mjs' },
    afterOverrides: { result } });
  assert.match(result.content.at(-1).text, /UNVERIFIED kind=tests/);
  assert.match(await visible(await h.json(`1 Tests bestanden. ${ref}`)), /UNVERIFIED/);
});

test('V2 rejects the HTTP context envelope as a Promise SDK context', async () => {
  const h = await setup();
  h.ctx.session.context = async () => ({ data: h.durable });
  const ref = await h.call();
  assert.match(await visible(await h.json(`Tests bestanden. ${ref}`)), /UNVERIFIED/);
});
for (const [name, override] of [
  ['missing emitted call', { emit: false }], ['missing before hook', { before: false }],
  ['tool error', { status: 'error' }],
  ['null exit', { result: { output: { output: SUMMARY, exit: null, truncated: false }, content: SUMMARY } }],
  ['failed exit', { result: { output: { output: SUMMARY, exit: 1, truncated: false }, content: SUMMARY } }],
  ['exit zero alone', { result: { output: { output: 'finished', exit: 0, truncated: false }, content: 'finished' } }],
  ['failed summary', { result: { output: { output: '# tests 2\n# pass 1\n# fail 1', exit: 0, truncated: false }, content: SUMMARY } }],
  ['running shell', { result: { output: { output: SUMMARY, exit: 0, truncated: false, status: 'running' }, content: SUMMARY } }],
  ['truncated shell', { result: { output: { output: SUMMARY, exit: 0, truncated: true }, content: SUMMARY } }],
  ['timed-out shell', { result: { output: { output: SUMMARY, exit: 0, truncated: false, timeout: true }, content: SUMMARY } }],
  ['signalled shell', { result: { output: { output: SUMMARY, exit: 0, truncated: false, signal: 'SIGTERM' }, content: SUMMARY } }],
  ['V1-shaped bash result', { tool: 'bash', result: { output: SUMMARY, metadata: { exit: 0 } } }],
  ['different before args', { beforeOverrides: { input: { command: 'node --test other.test.mjs' } } }],
  ['different after args', { afterOverrides: { input: { command: 'node --test other.test.mjs' } } }],
  ['different message identity', { afterOverrides: { messageID: 'msg_some_other_assistant' } }],
  ['different agent identity', { afterOverrides: { agent: 'other' } }],
  ['different session identity', { afterOverrides: { sessionID: 'ses_other' } }],
]) test(`V2 cannot certify tests with ${name}`, async () => {
  const h = await setup(); const ref = await h.call(override);
  assert.match(await visible(await h.json(`Tests bestanden. ${ref}`)), /UNVERIFIED/);
});
test('V2 native content array and structured shell output support an exact receipt', async () => {
  const h = await setup(); const ref = await h.call({ result: { output: { output: SUMMARY, exit: 0, truncated: false },
    content: [{ type: 'text', text: SUMMARY }], metadata: { exit: 0 } } });
  assert.equal(await visible(await h.json(`Tests bestanden. ${ref}`)), `Tests bestanden. ${ref}`);
});
test('V2 writing receipt still requires exact absolute claimed path', async () => {
  const h = await setup(); const ref = await h.call({ tool: 'write', args: { path: 'E:/fixture/a.txt', content: 'fixture' },
    result: { output: { operation: 'write', target: 'E:/fixture/a.txt', resource: 'a.txt', existed: true },
      content: 'Wrote file successfully: a.txt' } });
  assert.equal(await visible(await h.json(`Datei geändert: \`E:/fixture/a.txt\` ${ref}`)),
    `Datei geändert: \`E:/fixture/a.txt\` ${ref}`);
  assert.match(await visible(await h.json(`Datei geändert: \`E:/fixture/b.txt\` ${ref}`)), /UNVERIFIED/);
});
test('V2 a valid write receipt cannot certify test success', async () => {
  const h = await setup();
  const ref = await h.call({ tool: 'write', args: { path: 'E:/fixture/a.txt', content: 'fixture' },
    result: { output: { operation: 'write', target: 'E:/fixture/a.txt', resource: 'a.txt', existed: true },
      content: 'Wrote file successfully: a.txt' } });
  assert.notEqual(ref, '[GL:missing]');
  const supported = `Datei geändert: \`E:/fixture/a.txt\` ${ref}`;
  assert.equal(await visible(await h.json(supported)), supported);
  assert.equal(await visible(await h.json(`2 Tests bestanden. ${ref}`)),
    '[Guardrails UNVERIFIED: Erfolgsbehauptung ohne passenden aktuellen Beleg (tests).]');
});
test('V2 a valid test receipt cannot certify a changed file', async () => {
  const h = await setup(); const ref = await h.call();
  assert.notEqual(ref, '[GL:missing]');
  const supported = `2 Tests bestanden. ${ref}`;
  assert.equal(await visible(await h.json(supported)), supported);
  assert.equal(await visible(await h.json(`Datei geändert: \`E:/fixture/a.txt\` ${ref}`)),
    '[Guardrails UNVERIFIED: Erfolgsbehauptung ohne passenden aktuellen Beleg (write).]');
});
test('V2 synthetic or missing model user identities cannot authorize receipts', async () => {
  const h = await setup(); h.durable[0].type = 'synthetic';
  const ref = await h.call(); assert.match(await visible(await h.json(`Tests bestanden. ${ref}`)), /UNVERIFIED/);
});
test('V2 absent model message ID does not inherit newest durable user', async () => {
  const h = await setup(); await h.context({ messages: [{ role: 'user', content: [] }] });
  const req = await h.request({ contextFirst: false });
  const ref = await h.call({ req });
  assert.match(await visible(await h.json(`Tests bestanden. ${ref}`)), /UNVERIFIED/);
});
test('V2 late tools keep old task binding while new task cannot use their receipt', async () => {
  const h = await setup(); const old = await h.request();
  h.durable.push({ type: 'user', id: 'msg_user_b', text: 'New task' });
  await h.context({ user: 'msg_user_b' });
  const next = await h.request({ contextFirst: false });
  const ref = await h.call({ req: old });
  assert.match(await visible(await h.json(`Tests bestanden. ${ref}`, { req: next })), /UNVERIFIED/);
  assert.equal(await visible(await h.json(`Tests bestanden. ${ref}`)), `Tests bestanden. ${ref}`);
});
test('V2 concurrent native before hooks cannot exchange task identities', async () => {
  const h = await setup(); const args = { command: 'node --test tests/example.test.mjs' };
  const first = await h.request();
  await h.json(null, { req: first, tool_calls: [{ id: 'call_a', type: 'function', function: { name: 'shell', arguments: JSON.stringify(args) } }] });
  h.durable.push({ type: 'user', id: 'msg_user_b', text: 'Second task' });
  const second = await h.request({ user: 'msg_user_b' });
  await h.json(null, { req: second, tool_calls: [{ id: 'call_b', type: 'function', function: { name: 'shell', arguments: JSON.stringify(args) } }] });
  const before = id => h.toolHooks.get('execute.before')({ sessionID: 'ses_a', agent: 'build',
    messageID: 'msg_assistant_a', id, tool: 'shell', input: args });
  await Promise.all([before('call_a'), before('call_b')]);
  const refA = await h.call({ id: 'call_a', emit: false, before: false });
  const refB = await h.call({ id: 'call_b', emit: false, before: false });
  assert.equal(await visible(await h.json(`Tests bestanden. ${refA}`)), `Tests bestanden. ${refA}`);
  const b = await h.request({ user: 'msg_user_b' });
  assert.equal(await visible(await h.json(`Tests bestanden. ${refB}`, { req: b })), `Tests bestanden. ${refB}`);
});
test('V2 overlapping contexts without exact HTTP generation identity fail closed', async () => {
  const h = await setup(); await h.context(); await h.context();
  const req = await h.request({ contextFirst: false });
  const r = await h.json('Tests bestanden.', { req }); assert.equal(r.status, 422);
});
test('V2 response with cloned Request has no trusted correlation', async () => {
  const h = await setup(); const req = await h.request();
  const r = await h.json('Tests bestanden.', { req: { ...req, request: req.request.clone() } });
  assert.equal(r.status, 422); assert.match(await visible(r), /UNVERIFIED/);
});
test('V2 other provider requests are passed through without claiming protection', async () => {
  const h = await setup(); const req = await h.request({ model: { providerID: 'other', id: 'fixture' } });
  const original = new Response('provider-specific body');
  assert.equal(await h.response(req, original), original);
});
for (const endpoint of ['http://localhost:11434/v1/chat/completions',
  'https://127.0.0.1:11434/v1/chat/completions', 'http://127.0.0.1:11434/api/chat']) {
  test(`V2 unsupported Ollama endpoint fails closed: ${endpoint}`, async () => {
    const h = await setup({ endpoint }); const req = await h.request({ url: endpoint });
    const r = await h.json('Tests bestanden.', { req }); assert.equal(r.status, 422);
  });
}
test('V2 SSE fragmented content and refusal are checked together; tool and usage frames survive', async () => {
  const h = await setup(); const req = await h.request({ stream: true });
  const frames = [frame({ role: 'assistant', content: 'Tests ' }), frame({ refusal: 'bestanden.' }),
    frame({ reasoning_content: 'internal' }),
    frame({ tool_calls: [{ index: 0, id: 'call_stream', type: 'function', function: { name: 'shell', arguments: '{"command":' } }] }),
    frame({ tool_calls: [{ index: 0, function: { arguments: '"node --test a.test.mjs"}' } }] }),
    { ...frame({}), choices: [{ index: 0, delta: {}, finish_reason: 'tool_calls' }] },
    { ...frame({}), choices: [], usage: { prompt_tokens: 5, completion_tokens: 8, total_tokens: 13 } }, '[DONE]'];
  const r = await h.response(req, sse(frames), 'text/event-stream'); const text = await r.text();
  assert.equal(r.status, 200); assert.match(text, /UNVERIFIED/);
  assert.doesNotMatch(text, /"content":"Tests "/); assert.doesNotMatch(text, /"refusal":"bestanden\."/);
  assert.match(text, /reasoning_content/); assert.match(text, /call_stream/); assert.match(text, /prompt_tokens/);
  assert.match(text, /"finish_reason":"tool_calls"/); assert.match(text, /data: \[DONE\]\n\n$/);
  const ref = await h.call({ id: 'call_stream', args: { command: 'node --test a.test.mjs' }, emit: false });
  assert.equal(await visible(await h.json(`Tests bestanden. ${ref}`)), `Tests bestanden. ${ref}`);
});
test('V2 nonstream refusal success is checked and ordinary uncertainty is preserved', async () => {
  const h = await setup(); const r = await h.json(null, { refusal: 'Tests bestanden.' });
  assert.match((await r.json()).choices[0].message.refusal, /UNVERIFIED/);
  assert.equal(await visible(await h.json('Tests sind ungeprüft. Nächster Schritt: gezielt prüfen.')),
    'Tests sind ungeprüft. Nächster Schritt: gezielt prüfen.');
});
for (const [label, body, contentType] of [
  ['malformed JSON', '{broken', 'application/json'],
  ['unknown protocol', 'unreviewed text', 'text/plain'],
  ['missing SSE terminal', sse([frame({ content: 'Tests bestanden.' })]), 'text/event-stream'],
  ['malformed SSE JSON', 'data: {broken\n\ndata: [DONE]\n\n', 'text/event-stream'],
  ['multiple choices', JSON.stringify({ object: 'chat.completion', choices: [{ index: 0 }, { index: 1 }] }), 'application/json'],
  ['legacy function call', JSON.stringify({ object: 'chat.completion', choices: [{ index: 0,
    message: { role: 'assistant', content: null, function_call: { name: 'bash', arguments: '{}' } }, finish_reason: 'stop' }] }), 'application/json'],
]) test(`V2 ${label} returns a bounded guard error without original body/tool calls`, async () => {
  const h = await setup(); const req = await h.request({ stream: contentType === 'text/event-stream' });
  const r = await h.response(req, body, contentType); assert.equal(r.status, 422);
  const e = await r.json(); assert.match(e.error.message, /UNVERIFIED/); assert.equal(e.choices, undefined);
});
test('V2 size limit explicitly cancels unread original response', async () => {
  const h = await setup({ maxBytes: 256 }); const req = await h.request(); let cancelled = false;
  const stream = new ReadableStream({ start(c) { c.enqueue(new Uint8Array(300)); }, cancel() { cancelled = true; } });
  const r = await h.response(req, new Response(stream, { headers: { 'content-type': 'application/json' } }));
  assert.equal(r.status, 422); assert.equal(cancelled, true);
});
test('V2 timeout explicitly cancels a stalled original response', async () => {
  const h = await setup({ timeoutMs: 20 }); const req = await h.request(); let cancelled = false;
  const stream = new ReadableStream({ cancel() { cancelled = true; } });
  const r = await h.response(req, new Response(stream, { headers: { 'content-type': 'application/json' } }));
  assert.equal(r.status, 422); assert.equal(cancelled, true);
});
test('V2 request abort cancels original response before any replay', async () => {
  const h = await setup(); const controller = new AbortController();
  const req = await h.request({ signal: controller.signal }); let cancelled = false;
  const stream = new ReadableStream({ start() { controller.abort(); }, cancel() { cancelled = true; } });
  const r = await h.response(req, new Response(stream, { headers: { 'content-type': 'application/json' } }));
  assert.equal(r.status, 422); assert.equal(cancelled, true);
});
test('V2 rewritten responses remove stale encoding and length headers', async () => {
  const h = await setup(); const req = await h.request();
  const body = JSON.stringify({ object: 'chat.completion', choices: [{ index: 0,
    message: { role: 'assistant', content: 'Tests bestanden.' }, finish_reason: 'stop' }] });
  const r = await h.response(req, body, 'application/json', { headers: { 'content-length': '5', 'content-encoding': 'gzip' } });
  assert.equal(r.headers.get('content-length'), null); assert.equal(r.headers.get('content-encoding'), null);
  assert.match(await visible(r), /UNVERIFIED/);
});
test('V2 guard errors explicitly suppress native retries for the failed Ollama scope', async () => {
  const h = await setup(); const req = await h.request();
  const response = await h.response(req, '{malformed'); assert.equal(response.status, 422);
  assert.equal(typeof h.sessionHooks.get('retry'), 'function', 'guard error needs explicit retry control');
  const retry = { ...h.scope, error: { message: 'guard HTTP error' }, attempt: 1, decision: { retry: true, delay: 100 } };
  await h.sessionHooks.get('retry')(retry); assert.deepEqual(retry.decision, { retry: false });
  const other = { ...retry, model: { providerID: 'other', id: 'fixture' }, decision: { retry: true, delay: 100 } };
  await h.sessionHooks.get('retry')(other); assert.deepEqual(other.decision, { retry: true, delay: 100 });
});
test('V2 a successful checked request does not suppress unrelated native retry policy', async () => {
  const h = await setup(); await h.json('Noch ungeprüft.');
  assert.equal(typeof h.sessionHooks.get('retry'), 'function', 'retry control must preserve unfailed scope');
  const retry = { ...h.scope, error: { message: 'unrelated transport error' }, attempt: 1, decision: { retry: true, delay: 100 } };
  await h.sessionHooks.get('retry')(retry); assert.deepEqual(retry.decision, { retry: true, delay: 100 });
});

test('V2 an unbound native mutation invalidates existing test receipts', async () => {
  const h = await setup(); const ref = await h.call();
  const event = { sessionID: 'ses_a', agent: 'build', messageID: 'msg_unbound',
    id: 'call_unbound', tool: 'write', input: { path: 'E:/fixture/a.txt', content: 'changed' } };
  await h.toolHooks.get('execute.before')(event);
  await h.toolHooks.get('execute.after')({ ...event, status: 'completed', result: {
    output: { operation: 'write', target: 'E:/fixture/a.txt', resource: 'file', existed: true },
    content: [{ type: 'text', text: 'Wrote file successfully.' }],
  } });
  assert.match(await visible(await h.json(`Tests bestanden. ${ref}`)), /UNVERIFIED/);
  // Conservative invalidation must not permanently poison future genuine runs.
  const fresh = await h.call({ id: 'call_fresh' });
  const text = `Tests bestanden. ${fresh}`;
  assert.equal(await visible(await h.json(text)), text);
});

test('V2 unknown newest model user cannot inherit an older user receipt', async () => {
  const h = await setup(); const ref = await h.call();
  await h.context({ messages: [
    { role: 'user', id: 'msg_user_a', content: [] },
    { role: 'user', id: 'msg_unknown_b', content: [] },
  ] });
  const req = await h.request({ contextFirst: false });
  assert.match(await visible(await h.json(`Tests bestanden. ${ref}`, { req })), /UNVERIFIED/);
});

test('V2 unknown mutation during the awaited text check cannot release a stale success', async () => {
  const h = await setup(); const ref = await h.call();
  const originalGet = Map.prototype.get; let injected = false;
  try {
    // Inject the native action exactly when the asynchronous engine message
    // lookup yields. This deterministically exercises the real await boundary.
    Map.prototype.get = function(key) {
      const result = originalGet.call(this, key);
      if (!injected && typeof key === 'string' && key.startsWith('gl_')) {
        injected = true;
        queueMicrotask(() => h.toolHooks.get('execute.before')({ sessionID: 'ses_a',
          agent: 'build', messageID: 'msg_unknown', id: 'call_unknown_race', tool: 'write', input: {} }));
      }
      return result;
    };
    const result = await h.json(`Tests bestanden. ${ref}`);
    assert.ok(injected);
    assert.match(await visible(result), /UNVERIFIED/);
  } finally { Map.prototype.get = originalGet; }
});

test('V2 explicitly identified synthetic context does not invent a new user task', async () => {
  const h = await setup(); const ref = await h.call();
  h.durable.push({ type: 'synthetic', id: 'msg_synthetic' });
  await h.context({ messages: [
    { role: 'user', id: 'msg_user_a', content: [] },
    { role: 'user', id: 'msg_synthetic', content: [] },
  ] });
  const req = await h.request({ contextFirst: false });
  const text = `Tests bestanden. ${ref}`;
  assert.equal(await visible(await h.json(text, { req })), text);
});

const STATIC_UNVERIFIED_ERROR = { error: { type: 'guardrails_unverified',
  message: 'Guardrails UNVERIFIED: Modellantwort konnte innerhalb des begrenzten lokalen Protokolls nicht geprüft werden.' } };
const EMPTY_REASONING_SENTINEL = 'synthetic-internal-reasoning-must-not-leak';
const completionUsage = { prompt_tokens: 3, completion_tokens: 7, total_tokens: 10 };

function completedResponseFixture(format, fields, finishReason = 'stop') {
  const message = { role: 'assistant', reasoning_content: EMPTY_REASONING_SENTINEL, ...fields };
  if (format === 'JSON') return JSON.stringify({ id: 'chatcmpl_empty_fixture', object: 'chat.completion',
    model: 'synthetic-model-must-not-leak', usage: completionUsage,
    choices: [{ index: 0, message, finish_reason: finishReason }] });
  return sse([frame(message), { ...frame({}), choices: [{ index: 0, delta: {}, finish_reason: finishReason }] },
    { ...frame({}), choices: [], usage: completionUsage }, '[DONE]']);
}

async function assertStaticGuardErrorAndNoRetry(h, response) {
  assert.equal(response.status, 422);
  assert.equal(response.headers.get('x-guardrails-status'), 'unverified');
  assert.equal(response.headers.get('content-type'), 'application/json');
  const body = await response.json();
  assert.deepEqual(body, STATIC_UNVERIFIED_ERROR,
    '422 must keep the existing static error without model text, reasoning, usage or finish metadata');
  assert.equal(body.choices, undefined);
  assert.doesNotMatch(JSON.stringify(body), /synthetic-internal-reasoning|synthetic-model|usage|finish_reason|reasoning_content/);
  assert.equal(typeof h.sessionHooks.get('retry'), 'function');
  const retry = { ...h.scope, error: { message: 'guard HTTP error' }, attempt: 1,
    decision: { retry: true, delay: 100 } };
  await h.sessionHooks.get('retry')(retry);
  assert.deepEqual(retry.decision, { retry: false });
}

for (const format of ['JSON', 'SSE']) {
  for (const [label, fields, finishReason] of [
    ['null content', { content: null }],
    ['missing content', {}],
    ['empty content', { content: '' }],
    ['JS-trimmable whitespace content', { content: ' \t\r\n\u00a0\ufeff ' }],
    ['reasoning-only content', { reasoning: 'synthetic-internal-reasoning-alternative' }],
    ['empty refusal', { content: null, refusal: '' }],
    ['empty tool_calls', { content: null, tool_calls: [] }, 'tool_calls'],
  ]) test(`V2 complete ${format} ${label} returns static 422 and disables retry`, async () => {
    const h = await setup();
    const req = await h.request({ stream: format === 'SSE' });
    const response = await h.response(req, completedResponseFixture(format, fields, finishReason),
      format === 'SSE' ? 'text/event-stream' : 'application/json');
    await assertStaticGuardErrorAndNoRetry(h, response);
  });

  for (const [label, fields, expectedField, expectedText] of [
    ['ordinary visible text', { content: 'Noch ungeprüft.' }, 'content', 'Noch ungeprüft.'],
    ['nonempty refusal', { content: null, refusal: 'Dabei kann ich nicht helfen.' }, 'refusal', 'Dabei kann ich nicht helfen.'],
  ]) test(`V2 complete ${format} preserves ${label} with HTTP 200`, async () => {
    const h = await setup();
    const req = await h.request({ stream: format === 'SSE' });
    const response = await h.response(req, completedResponseFixture(format, fields),
      format === 'SSE' ? 'text/event-stream' : 'application/json');
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('x-guardrails-status'), 'checked-bounded');
    const text = await response.text();
    if (format === 'JSON') assert.equal(JSON.parse(text).choices[0].message[expectedField], expectedText);
    else {
      const values = text.split('\n\n').filter(block => block.startsWith('data: {'))
        .map(block => JSON.parse(block.slice(6)));
      assert.equal(values.flatMap(value => value.choices).map(choice => choice.delta[expectedField] ?? '').join(''), expectedText);
      assert.match(text, /data: \[DONE\]\n\n$/);
    }
  });

  test(`V2 complete ${format} valid tool calls without text remain usable with HTTP 200`, async () => {
    const h = await setup();
    const req = await h.request({ stream: format === 'SSE' });
    const args = { command: 'node --test tests/example.test.mjs' };
    const call = { id: 'call_empty_control', type: 'function',
      function: { name: 'shell', arguments: JSON.stringify(args) } };
    const body = format === 'JSON'
      ? completedResponseFixture(format, { content: null, tool_calls: [call] }, 'tool_calls')
      : sse([frame({ role: 'assistant', content: null, tool_calls: [{ index: 0, id: call.id,
        type: 'function', function: { name: 'shell', arguments: '{"command":' } }] }),
      frame({ tool_calls: [{ index: 0, function: { arguments: '"node --test tests/example.test.mjs"}' } }] }),
      { ...frame({}), choices: [{ index: 0, delta: {}, finish_reason: 'tool_calls' }] }, '[DONE]']);
    const response = await h.response(req, body, format === 'SSE' ? 'text/event-stream' : 'application/json');
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('x-guardrails-status'), 'checked-bounded');
    const text = await response.text();
    if (format === 'JSON') assert.deepEqual(JSON.parse(text).choices[0].message.tool_calls, [call]);
    else {
      assert.match(text, /call_empty_control/);
      assert.match(text, /"finish_reason":"tool_calls"/);
      assert.match(text, /data: \[DONE\]\n\n$/);
    }
    const receipt = await h.call({ id: call.id, args, req, emit: false });
    assert.notEqual(receipt, '[GL:missing]');
    const supported = `2 Tests bestanden. ${receipt}`;
    assert.equal(await visible(await h.json(supported)), supported);
  });

  test(`V2 complete empty ${format} after a genuine scoped tool receipt still returns static 422`, async () => {
    const h = await setup();
    const receipt = await h.call();
    assert.notEqual(receipt, '[GL:missing]');
    const supported = `2 Tests bestanden. ${receipt}`;
    assert.equal(await visible(await h.json(supported)), supported);
    const req = await h.request({ stream: format === 'SSE' });
    const response = await h.response(req, completedResponseFixture(format, { content: null }),
      format === 'SSE' ? 'text/event-stream' : 'application/json');
    await assertStaticGuardErrorAndNoRetry(h, response);
  });
}

test('V2 interrupted SSE keeps the existing static 422 error and retry suppression', async () => {
  const h = await setup();
  const req = await h.request({ stream: true });
  let streamController;
  const stream = new ReadableStream({ start(controller) {
    streamController = controller;
    controller.enqueue(new TextEncoder().encode(sse([frame({ content: 'Noch ungeprüft.',
      reasoning_content: EMPTY_REASONING_SENTINEL })])));
  } });
  const pending = h.response(req, new Response(stream, { headers: { 'content-type': 'text/event-stream' } }));
  await new Promise(resolve => setImmediate(resolve));
  streamController.error(new Error('synthetic-internal-reasoning-stream-abort'));
  await assertStaticGuardErrorAndNoRetry(h, await pending);
});

for (const [label, fields, expectsError] of [
  ['visible answer', { content: 'Noch ungeprüft.' }, false],
  ['empty answer', { content: null, reasoning_content: EMPTY_REASONING_SENTINEL }, true],
]) test(`V2 SSE ${label} stays buffered until final frame, DONE and stream close`, async () => {
  const h = await setup();
  const req = await h.request({ stream: true });
  let streamController;
  const stream = new ReadableStream({ start(controller) {
    streamController = controller;
    controller.enqueue(new TextEncoder().encode(sse([frame(fields)])));
  } });
  let settled = false;
  const pending = h.response(req, new Response(stream, { headers: { 'content-type': 'text/event-stream' } }))
    .then(response => { settled = true; return response; });
  try {
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(settled, false, 'an answer cannot escape before the complete buffered SSE body');
  } finally {
    streamController.enqueue(new TextEncoder().encode(sse([
      { ...frame({}), choices: [{ index: 0, delta: {}, finish_reason: 'stop' }] }, '[DONE]'])));
    streamController.close();
  }
  const response = await pending;
  if (expectsError) await assertStaticGuardErrorAndNoRetry(h, response);
  else {
    assert.equal(response.status, 200);
    assert.match(await response.text(), /data: \[DONE\]\n\n$/);
  }
});
