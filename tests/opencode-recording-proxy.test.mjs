import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import { syncBuiltinESMExports } from 'node:module';
import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRecordingProxy } from '../tools/opencode/recording-proxy.mjs';

const exec = promisify(execFile);
const completion = '/v1/chat/completions';
const metadata = '/api/tags';
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const proxyTest = (name, run) => test(name, { timeout: 6000 }, run);

function deadline(promise, label, ms = 2500) {
  let timer;
  return Promise.race([promise, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`Timed out: ${label}`)), ms);
  })]).finally(() => clearTimeout(timer));
}

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

async function readRequest(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return Buffer.concat(chunks);
}

function request(url, { method = 'POST', path = completion, body,
  headers = {}, chunks } = {}) {
  return new Promise((resolve, reject) => {
    const target = new URL(path, url);
    const req = http.request(target, { method, agent: false, headers }, res => {
      const received = [];
      res.on('data', chunk => received.push(chunk));
      res.on('error', finish);
      res.on('aborted', () => finish(new Error('Client response aborted')));
      res.on('end', () => finish(null, { status: res.statusCode,
        headers: res.headers, body: Buffer.concat(received) }));
    });
    let settled = false;
    const timer = setTimeout(() => req.destroy(new Error('Client absolute timeout')), 3500);
    function finish(error, result) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(result);
    }
    req.on('error', finish);
    if (chunks) {
      (async () => {
        for (const chunk of chunks) {
          if (req.destroyed) return;
          req.write(chunk);
          await delay(2);
        }
        req.end();
      })().catch(error => req.destroy(error));
    } else req.end(body ?? (method === 'POST' ? Buffer.from('{}') : Buffer.alloc(0)));
  });
}

async function fixture(t, handler = async (req, res) => {
  await readRequest(req);
  res.writeHead(200, { 'content-type': 'application/json' });
  res.end('{"fixture":true}');
}, options = {}) {
  const root = await mkdtemp(join(tmpdir(), 'guardrails-recording-proxy-'));
  const outputDir = join(root, 'capture');
  const sockets = new Set();
  let contacts = 0;
  const server = http.createServer((req, res) => {
    contacts++;
    Promise.resolve(handler(req, res)).catch(() => res.destroy());
  });
  server.on('connection', socket => {
    sockets.add(socket);
    socket.on('close', () => sockets.delete(socket));
  });
  let proxy;
  let stopped = false;
  async function stop() {
    if (stopped) return;
    stopped = true;
    try {
      if (proxy) await deadline(proxy.close(), 'proxy.close');
    } finally {
      for (const socket of sockets) socket.destroy();
      if (server.listening) await deadline(new Promise(resolve => server.close(resolve)), 'fixture close');
    }
  }
  t.after(async () => {
    try { await stop(); }
    finally { await rm(root, { recursive: true, force: true }); }
  });
  await deadline(new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  }), 'fixture listen');
  const upstream = `http://127.0.0.1:${server.address().port}`;
  proxy = await createRecordingProxy({ upstream, outputDir, ...options });
  assert.equal(new URL(proxy.url).hostname, '127.0.0.1');
  assert.notEqual(Number(new URL(proxy.url).port), 0);
  return { root, outputDir, upstream, proxy, stop, contacts: () => contacts,
    request: options => request(proxy.url, options) };
}

async function captures(outputDir) {
  const entries = (await readdir(outputDir, { withFileTypes: true }))
    .filter(entry => entry.isDirectory()).map(entry => entry.name).sort();
  return Promise.all(entries.map(async name => {
    assert.match(name, /^\d{4}-(completion|metadata)$/);
    const folder = join(outputDir, name);
    const [requestBody, responseBody, text] = await Promise.all([
      readFile(join(folder, 'request.body')), readFile(join(folder, 'response.body')),
      readFile(join(folder, 'capture.json'), 'utf8'),
    ]);
    return { name, requestBody, responseBody, text, info: JSON.parse(text) };
  }));
}

function checkCapture(capture, { sequence, method = 'POST', route = completion,
  maxBytes = 1048576 } = {}) {
  const { info, requestBody, responseBody, name } = capture;
  assert.equal(info.schema, 1);
  assert.equal(info.sequence, sequence);
  assert.equal(Number(name.slice(0, 4)), sequence);
  assert.equal(info.method, method);
  assert.equal(info.route, route);
  assert.ok(['COMPLETE', 'PARTIAL', 'ERROR'].includes(info.status));
  for (const [part, bytes] of [[info.request, requestBody], [info.response, responseBody]]) {
    assert.equal(part.bytes, bytes.length);
    assert.equal(part.sha256, sha256(bytes));
    assert.equal(typeof part.complete, 'boolean');
    assert.ok(bytes.length <= maxBytes, 'capture must respect the configured byte limit');
  }
  assert.ok(info.response.http_status === null || Number.isInteger(info.response.http_status));
  assert.ok(info.response.content_type === null || typeof info.response.content_type === 'string');
  assert.ok([true, false, null].includes(info.response.sse_done_seen));
  if (info.status === 'COMPLETE') {
    assert.equal(info.reason, null);
    assert.equal(info.request.complete, true);
    assert.equal(info.response.complete, true);
  } else {
    assert.equal(typeof info.reason, 'string');
    assert.ok(info.reason.length > 0);
  }
}

function checkFailure(capture, options) {
  checkCapture(capture, options);
  assert.notEqual(capture.info.status, 'COMPLETE');
}

proxyTest('import alone exits without creating a listener or requiring configuration', async () => {
  const moduleUrl = new URL('../tools/opencode/recording-proxy.mjs', import.meta.url).href;
  const result = await exec(process.execPath, ['--input-type=module', '--eval',
    `await import(${JSON.stringify(moduleUrl)});`], { timeout: 2000 });
  assert.equal(result.stdout, '');
  assert.equal(result.stderr, '');
});

proxyTest('starting the proxy makes no upstream request; metadata gets its own sequence', async t => {
  const h = await fixture(t);
  await delay(30);
  assert.equal(h.contacts(), 0);
  assert.equal((await h.request({ method: 'GET', path: metadata, body: undefined })).status, 200);
  assert.equal((await h.request()).status, 200);
  await h.stop();
  const saved = await captures(h.outputDir);
  assert.deepEqual(saved.map(c => c.name), ['0001-metadata', '0002-completion']);
  checkCapture(saved[0], { sequence: 1, method: 'GET', route: metadata });
  checkCapture(saved[1], { sequence: 2 });
  assert.equal(saved[0].requestBody.length, 0);
});

proxyTest('JSON preserves exact request and response bytes, status, content type and hashes', async t => {
  const sent = Buffer.from('{\n "model" : "fixture", "messages":[{"content":"Grüße 👋"}] }\n');
  const reply = Buffer.from(' { "answer" : "größer 👋", "n":1.00 }\n');
  let upstreamBody;
  const h = await fixture(t, async (req, res) => {
    assert.equal(req.method, 'POST');
    assert.equal(req.url, completion);
    upstreamBody = await readRequest(req);
    res.writeHead(201, { 'content-type': 'application/json; charset=utf-8' });
    res.end(reply);
  });
  const received = await h.request({ body: sent, headers: {
    'content-type': 'application/json', authorization: 'Bearer synthetic-header-token',
  } });
  assert.equal(received.status, 201);
  assert.equal(received.headers['content-type'], 'application/json; charset=utf-8');
  assert.deepEqual(received.body, reply);
  assert.deepEqual(upstreamBody, sent);
  await h.stop();
  const saved = await captures(h.outputDir);
  assert.equal(saved.length, 1);
  checkCapture(saved[0], { sequence: 1 });
  assert.equal(saved[0].info.status, 'COMPLETE');
  assert.equal(saved[0].info.response.http_status, 201);
  assert.equal(saved[0].info.response.content_type, 'application/json; charset=utf-8');
  assert.equal(saved[0].info.response.sse_done_seen, null);
  assert.deepEqual(saved[0].requestBody, sent);
  assert.deepEqual(saved[0].responseBody, reply);
  assert.ok(!saved[0].text.includes('synthetic-header-token'));
});

proxyTest('fragmented UTF-8 and split SSE DONE bytes survive without reserialization', async t => {
  const reply = Buffer.from('data: {"choices":[{"delta":{"content":"Grüße 👋"}}]}\r\n\r\ndata: [DONE]\r\n\r\n');
  const umlaut = reply.indexOf(Buffer.from('ü'));
  const emoji = reply.indexOf(Buffer.from('👋'));
  const done = reply.indexOf(Buffer.from('[DONE]'));
  const cuts = [0, umlaut + 1, emoji + 2, done + 3, reply.length];
  const sent = Buffer.from('{ "prompt": "Grüße 👋" }');
  const requestCut = sent.indexOf(Buffer.from('ü')) + 1;
  let upstreamBody;
  const h = await fixture(t, async (req, res) => {
    upstreamBody = await readRequest(req);
    res.writeHead(200, { 'content-type': 'text/event-stream; charset=utf-8' });
    for (let i = 1; i < cuts.length; i++) {
      res.write(reply.subarray(cuts[i - 1], cuts[i]));
      await delay(2);
    }
    res.end();
  });
  const result = await h.request({ chunks: [sent.subarray(0, requestCut), sent.subarray(requestCut)] });
  assert.equal(result.status, 200);
  assert.deepEqual(result.body, reply);
  assert.deepEqual(upstreamBody, sent);
  await h.stop();
  const [saved] = await captures(h.outputDir);
  checkCapture(saved, { sequence: 1 });
  assert.equal(saved.info.status, 'COMPLETE');
  assert.equal(saved.info.response.complete, true);
  assert.equal(saved.info.response.sse_done_seen, true);
  assert.deepEqual(saved.requestBody, sent);
  assert.deepEqual(saved.responseBody, reply);
});

proxyTest('a complete SSE response without DONE remains HTTP-complete with marker false', async t => {
  const body = Buffer.from('data: {"choices":[{"delta":{"content":"fixture"}}]}\n\n');
  const h = await fixture(t, async (req, res) => {
    await readRequest(req);
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    res.end(body);
  });
  assert.deepEqual((await h.request()).body, body);
  await h.stop();
  const [saved] = await captures(h.outputDir);
  checkCapture(saved, { sequence: 1 });
  assert.equal(saved.info.status, 'COMPLETE');
  assert.equal(saved.info.response.complete, true);
  assert.equal(saved.info.response.sse_done_seen, false);
});

proxyTest('only explicit numeric IPv4 HTTP upstream origins are accepted', async t => {
  const root = await mkdtemp(join(tmpdir(), 'guardrails-proxy-invalid-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const invalid = ['http://localhost:1', 'http://[::1]:1', 'http://0.0.0.0:1',
    'https://127.0.0.1:1', 'http://127.0.0.1:1/path', 'http://127.0.0.1:1/?x=1',
    'http://user:pass@127.0.0.1:1', 'http://127.0.0.1:1/#fragment',
    'http://127.0.0.1', 'http://127.0.0.1:0'];
  for (let i = 0; i < invalid.length; i++) {
    await assert.rejects(async () => {
      const proxy = await createRecordingProxy({ upstream: invalid[i], outputDir: join(root, `bad-${i}`) });
      await proxy.close();
    }, `must reject ${invalid[i]}`);
  }
});

proxyTest('output directory must be new and absolute with an existing parent', async t => {
  const root = await mkdtemp(join(tmpdir(), 'guardrails-proxy-paths-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const existing = join(root, 'existing');
  await mkdir(existing);
  await writeFile(join(existing, 'keep.txt'), 'keep this fixture');
  const file = join(root, 'existing-file');
  await writeFile(file, 'keep file');
  for (const outputDir of [existing, file, 'relative-capture', join(root, 'missing-parent', 'capture')]) {
    await assert.rejects(async () => {
      const proxy = await createRecordingProxy({ upstream: 'http://127.0.0.1:1', outputDir });
      await proxy.close();
    });
  }
  assert.equal(await readFile(join(existing, 'keep.txt'), 'utf8'), 'keep this fixture');
  assert.equal(await readFile(file, 'utf8'), 'keep file');
});

proxyTest('unknown methods, routes and query variants never reach upstream', async t => {
  const h = await fixture(t);
  for (const [method, path] of [['GET', completion], ['POST', metadata],
    ['POST', '/v1/chat/completions?x=1'], ['GET', '/api/tags?x=1'],
    ['POST', '/other'], ['POST', '/v1/chat/completions/'], ['DELETE', completion]]) {
    assert.equal((await h.request({ method, path })).status, 404, `${method} ${path}`);
  }
  assert.equal(h.contacts(), 0);
});

proxyTest('upstream redirects return 502 without following their location', async t => {
  const h = await fixture(t, async (req, res) => {
    await readRequest(req);
    res.writeHead(307, { location: '/redirect-target', 'content-type': 'text/plain' });
    res.end('redirect fixture');
  });
  assert.equal((await h.request()).status, 502);
  assert.equal(h.contacts(), 1);
  await h.stop();
  const [saved] = await captures(h.outputDir);
  checkFailure(saved, { sequence: 1 });
});

proxyTest('metadata does not consume two permanent completion places', async t => {
  const h = await fixture(t);
  for (let i = 0; i < 3; i++) assert.equal((await h.request({ method: 'GET', path: metadata })).status, 200);
  assert.equal((await h.request()).status, 200);
  assert.equal((await h.request()).status, 200);
  assert.equal((await h.request()).status, 429);
  assert.equal(h.contacts(), 5);
});

proxyTest('completion places are reserved before asynchronous work under parallel requests', async t => {
  const entered = deferred();
  const release = deferred();
  let count = 0;
  const h = await fixture(t, async (req, res) => {
    await readRequest(req);
    if (++count === 2) entered.resolve();
    await release.promise;
    res.end('fixture');
  });
  t.after(() => release.resolve());
  const first = h.request();
  const second = h.request();
  try {
    await deadline(entered.promise, 'two accepted completions');
    assert.equal((await h.request()).status, 429);
    assert.equal(h.contacts(), 2);
  } finally { release.resolve(); }
  assert.deepEqual((await Promise.all([first, second])).map(r => r.status), [200, 200]);
});

proxyTest('failed completion attempts still consume their reserved places', async t => {
  const h = await fixture(t, async (req, res) => {
    await readRequest(req);
    res.destroy();
  });
  assert.equal((await h.request()).status, 502);
  assert.equal((await h.request()).status, 502);
  assert.equal((await h.request()).status, 429);
  assert.equal(h.contacts(), 2);
  await h.stop();
  const saved = await captures(h.outputDir);
  assert.equal(saved.length, 2);
  saved.forEach((capture, i) => checkFailure(capture, { sequence: i + 1 }));
});

proxyTest('at most ten metadata requests are accepted per instance', async t => {
  const h = await fixture(t);
  for (let i = 0; i < 10; i++) assert.equal((await h.request({ method: 'GET', path: metadata })).status, 200);
  assert.equal((await h.request({ method: 'GET', path: metadata })).status, 429);
  assert.equal(h.contacts(), 10);
  await h.stop();
  const saved = await captures(h.outputDir);
  assert.equal(saved.length, 10);
  saved.forEach((capture, i) => checkCapture(capture, { sequence: i + 1, method: 'GET', route: metadata }));
});

proxyTest('oversized request returns 413 and retains only bounded original request bytes', async t => {
  const limit = 64;
  const body = Buffer.from('x'.repeat(65));
  const h = await fixture(t, undefined, { maxBytes: limit });
  assert.equal((await h.request({ body })).status, 413);
  assert.equal(h.contacts(), 0);
  await h.stop();
  const [saved] = await captures(h.outputDir);
  checkFailure(saved, { sequence: 1, maxBytes: limit });
  assert.equal(saved.info.request.complete, false);
  assert.ok(saved.requestBody.length > 0);
  assert.deepEqual(saved.requestBody, body.subarray(0, saved.requestBody.length));
});

proxyTest('default body limit rejects a request larger than one MiB', async t => {
  const h = await fixture(t);
  assert.equal((await h.request({ body: Buffer.alloc(1048577, 0x61) })).status, 413);
  assert.equal(h.contacts(), 0);
  await h.stop();
  const [saved] = await captures(h.outputDir);
  checkFailure(saved, { sequence: 1 });
  assert.equal(saved.info.request.complete, false);
});

proxyTest('oversized upstream response returns 502 and keeps a bounded byte prefix', async t => {
  const body = Buffer.from('ö'.repeat(50));
  const h = await fixture(t, async (req, res) => {
    await readRequest(req);
    res.writeHead(200, { 'content-type': 'text/plain; charset=utf-8' });
    res.end(body);
  }, { maxBytes: 64 });
  assert.equal((await h.request()).status, 502);
  await h.stop();
  const [saved] = await captures(h.outputDir);
  checkFailure(saved, { sequence: 1, maxBytes: 64 });
  assert.equal(saved.info.response.complete, false);
  assert.ok(saved.responseBody.length > 0);
  assert.deepEqual(saved.responseBody, body.subarray(0, saved.responseBody.length));
});

proxyTest('absolute deadline returns 504 even while upstream keeps sending bytes', async t => {
  const h = await fixture(t, async (req, res) => {
    await readRequest(req);
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    res.write('data: start\n\n');
    const timer = setInterval(() => res.write(': tick\n\n'), 15);
    res.once('close', () => clearInterval(timer));
  }, { timeoutMs: 120 });
  const started = performance.now();
  assert.equal((await h.request()).status, 504);
  assert.ok(performance.now() - started < 1800, 'trickle must not restart the deadline');
  await h.stop();
  const [saved] = await captures(h.outputDir);
  checkFailure(saved, { sequence: 1 });
  assert.equal(saved.info.request.complete, true);
  assert.equal(saved.info.response.complete, false);
  assert.ok(saved.responseBody.length > 0);
  assert.equal(saved.info.response.sse_done_seen, false);
});

proxyTest('upstream abort preserves response prefix but cannot report COMPLETE or HTTP 200', async t => {
  const prefix = Buffer.from('data: {"choices":[{"delta":{"content":"Grüße"}}]}\n\n');
  const h = await fixture(t, async (req, res) => {
    await readRequest(req);
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    res.write(prefix);
    await delay(25);
    res.destroy();
  });
  assert.equal((await h.request()).status, 502);
  await h.stop();
  const [saved] = await captures(h.outputDir);
  checkFailure(saved, { sequence: 1 });
  assert.equal(saved.info.response.complete, false);
  assert.equal(saved.info.response.sse_done_seen, false);
  assert.deepEqual(saved.responseBody, prefix);
});

proxyTest('capture write failure prevents an unchecked success response', async t => {
  const upstreamEntered = deferred();
  const release = deferred();
  const h = await fixture(t, async (req, res) => {
    await readRequest(req);
    upstreamEntered.resolve();
    await release.promise;
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end('{"fixture":"must be recorded"}');
  });
  const pending = h.request();
  try {
    await deadline(upstreamEntered.promise, 'upstream request before disk failure');
    // The owned fixture directory is replaced by a file; this also works on Windows
    // without depending on chmod semantics or access to another user's files.
    await rm(h.outputDir, { recursive: true, force: true });
    await writeFile(h.outputDir, 'synthetic output obstruction');
  } finally { release.resolve(); }
  assert.equal((await pending).status, 502);
  await h.stop();
  assert.equal(await readFile(h.outputDir, 'utf8'), 'synthetic output obstruction');
});

proxyTest('close ends active connections and waits for the final partial capture', async t => {
  const entered = deferred();
  const prefix = Buffer.from('data: partial fixture\n\n');
  const h = await fixture(t, async (req, res) => {
    await readRequest(req);
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    res.write(prefix);
    entered.resolve();
  });
  const pending = h.request().then(response => ({ response }), error => ({ error }));
  await deadline(entered.promise, 'active response before close');
  await delay(20);
  await h.stop();
  const outcome = await deadline(pending, 'closed client');
  if (outcome.response) assert.notEqual(outcome.response.status, 200);
  await assert.rejects(request(h.proxy.url, { method: 'GET', path: metadata }));
  const [saved] = await captures(h.outputDir);
  checkFailure(saved, { sequence: 1 });
  assert.equal(saved.info.response.complete, false);
  assert.deepEqual(saved.responseBody, prefix);
});

proxyTest('deadline responds while capture disk I/O is still pending', async t => {
  const entered = deferred(), release = deferred();
  const original = fs.writeFile;
  let blocked = false;
  fs.writeFile = async (file, ...args) => {
    if (!blocked && String(file).endsWith('response.body')) {
      blocked = true; entered.resolve(); await release.promise;
    }
    return original(file, ...args);
  };
  syncBuiltinESMExports();
  let pending, h;
  try {
    h = await fixture(t, undefined, { timeoutMs: 120 });
    pending = h.request();
    await deadline(entered.promise, 'blocked capture write');
    const early = await Promise.race([pending, delay(500).then(() => null)]);
    assert.equal(early?.status, 504, '504 must not wait for capture storage');
  } finally {
    fs.writeFile = original; syncBuiltinESMExports(); release.resolve();
    if (pending) await pending;
  }
  await h.stop();
  const [saved] = await captures(h.outputDir);
  checkFailure(saved, { sequence: 1 });
});
