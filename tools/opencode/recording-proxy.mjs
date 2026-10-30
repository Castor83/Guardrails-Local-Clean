// Bounded local HTTP entity-body recorder. No model client, configuration edits,
// startup probes, automatic retries, DNS targets or import-time listeners.
import http from 'node:http';
import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { isAbsolute, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const MAX_BYTES = 1_048_576, MAX_MS = 60_000;
const stamp = () => new Date().toISOString();
const hash = body => createHash('sha256').update(body).digest('hex');
const failure = (reason, status = 502) => Object.assign(new Error(reason), { reason, status });
const bodyState = () => ({ chunks: [], bytes: 0, complete: false });
const bytes = state => Buffer.concat(state.chunks, state.bytes);
function checkSignal(signal) {
  if (signal.aborted) throw failure(signal.reason === 'timeout' ? 'timeout' : 'cancelled',
    signal.reason === 'timeout' ? 504 : 502);
}
function boundedBody(stream, state, limit, signal, tooLarge) {
  return new Promise((resolveBody, reject) => {
    let settled = false;
    // A destroyed stream may emit a subsequent error after the collector settles.
    stream.on('error', () => {});
    function finish(error) {
      if (settled) return;
      settled = true;
      stream.off('data', data); stream.off('end', end); stream.off('error', errorEvent);
      stream.off('close', close); signal.removeEventListener('abort', abort);
      if (error) reject(error); else resolveBody();
    }
    function data(chunk) {
      const remaining = limit - state.bytes;
      if (remaining > 0) {
        const kept = Buffer.from(chunk.subarray(0, remaining));
        state.chunks.push(kept); state.bytes += kept.length;
      }
      if (chunk.length > remaining) { stream.pause(); finish(tooLarge); }
    }
    function end() {
      state.complete = stream.complete === true;
      finish(state.complete ? null : failure('incomplete_body'));
    }
    function errorEvent() { finish(failure('incomplete_body')); }
    function close() { if (!settled) finish(failure('incomplete_body')); }
    function abort() {
      try { checkSignal(signal); } catch (error) { stream.pause(); finish(error); }
    }
    stream.on('data', data); stream.once('end', end); stream.once('error', errorEvent);
    stream.once('close', close); signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) abort();
  });
}
function headersFor(headers, length) {
  const blocked = new Set(['connection', 'keep-alive', 'proxy-authenticate',
    'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade', 'host',
    'content-length', ...(headers.connection ?? '').split(',').map(x => x.trim().toLowerCase())]);
  return { ...Object.fromEntries(Object.entries(headers).filter(([key]) => !blocked.has(key))),
    'content-length': String(length), connection: 'close' };
}
function replyError(res, status) {
  if (res.destroyed || res.writableEnded) return;
  res.writeHead(status, { 'content-type': 'application/json', connection: 'close' });
  res.end(JSON.stringify({ error: 'recording_proxy_unverified', status }));
}

export async function createRecordingProxy({ upstream, outputDir, port = 0,
  maxBytes = MAX_BYTES, timeoutMs = MAX_MS } = {}) {
  const target = typeof upstream === 'string' && /^http:\/\/127\.0\.0\.1:([1-9]\d{0,4})\/?$/.exec(upstream);
  if (!target || +target[1] > 65535) throw Error('Explicit http://127.0.0.1:PORT upstream required');
  if (typeof outputDir !== 'string' || !isAbsolute(outputDir)) throw Error('New absolute outputDir required');
  if (!Number.isInteger(port) || port < 0 || port > 65535 ||
    !Number.isInteger(maxBytes) || maxBytes < 1 || maxBytes > MAX_BYTES ||
    !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > MAX_MS) throw Error('Invalid proxy bounds');
  await mkdir(outputDir, { mode: 0o700 }); // Intentionally not recursive; EEXIST must fail.
  await writeFile(join(outputDir, 'session.json'), JSON.stringify({ schema: 1,
    started_at: stamp(), upstream, maxBytes, timeoutMs, max_completions: 2,
    max_http_requests: 10, capture: 'HTTP entity bytes; buffered; not wire framing' }, null, 2), { flag: 'wx' });
  let accepted = 0, completions = 0, rejected = 0, closing = false, closePromise;
  const jobs = new Set(), controllers = new Set(), sockets = new Set();
  const counts = { complete: 0, failed: 0, capture_write_failures: 0 };

  async function capture(req, res, sequence, kind) {
    const control = new AbortController(), signal = control.signal;
    controllers.add(control);
    const timer = setTimeout(() => {
      control.abort('timeout');
      // The client deadline must not wait for an outstanding filesystem promise.
      replyError(res, 504);
    }, timeoutMs);
    const disconnected = () => { if (!res.writableFinished) control.abort('client_closed'); };
    res.once('close', disconnected);
    const request = bodyState(), response = bodyState();
    const folder = join(outputDir, `${String(sequence).padStart(4, '0')}-${kind}`);
    let owned = false, requestSaved = false, responseSaved = false, metaSaved = false;
    let upstreamResponse, upstreamRequest, status = null, contentType = null, encoding = null;
    const startedAt = stamp();
    async function save(error = null) {
      if (!owned) throw failure('capture_write_failed');
      const requestBody = bytes(request), responseBody = bytes(response);
      if (!requestSaved) {
        await writeFile(join(folder, 'request.body'), requestBody, { flag: 'wx' }); requestSaved = true;
      }
      if (!responseSaved) {
        await writeFile(join(folder, 'response.body'), responseBody, { flag: 'wx' }); responseSaved = true;
      }
      if (!error) checkSignal(signal); // Late storage completion cannot certify a timed-out exchange.
      const part = (state, body) => ({ bytes: body.length, sha256: hash(body), complete: state.complete });
      const sse = /^text\/event-stream(?:;|$)/i.test(contentType ?? '');
      const marker = sse && (!encoding || encoding === 'identity')
        ? /(?:^|\r?\n)data: ?\[DONE\](?:\r?\n|$)/.test(responseBody.toString('utf8')) : null;
      const record = { schema: 1, sequence, method: req.method, route: req.url,
        started_at: startedAt, finished_at: stamp(), status: error
          ? (request.bytes || response.bytes ? 'PARTIAL' : 'ERROR') : 'COMPLETE',
        reason: error?.reason ?? null, request: part(request, requestBody),
        response: { ...part(response, responseBody), http_status: status,
          content_type: contentType, content_encoding: encoding, sse_done_seen: marker } };
      await writeFile(join(folder, 'capture.json'), JSON.stringify(record, null, 2),
        { flag: metaSaved ? 'w' : 'wx' });
      metaSaved = true;
    }
    try {
      await mkdir(folder, { mode: 0o700 }); owned = true; checkSignal(signal);
      await boundedBody(req, request, maxBytes, signal, failure('request_too_large', 413));
      checkSignal(signal);
      await writeFile(join(folder, 'request.body'), bytes(request), { flag: 'wx' }); requestSaved = true;
      checkSignal(signal);
      upstreamResponse = await new Promise((resolveResponse, rejectResponse) => {
        upstreamRequest = http.request({ hostname: '127.0.0.1', port: +target[1],
          path: req.url, method: req.method, agent: false, signal,
          headers: headersFor(req.headers, request.bytes) }, resolveResponse);
        upstreamRequest.on('error', () => rejectResponse(failure('upstream_connection_failed')));
        upstreamRequest.end(bytes(request));
      });
      status = upstreamResponse.statusCode;
      contentType = upstreamResponse.headers['content-type'] ?? null;
      encoding = upstreamResponse.headers['content-encoding'] ?? null;
      await boundedBody(upstreamResponse, response, maxBytes, signal, failure('response_too_large'));
      checkSignal(signal);
      if (status >= 300 && status < 400) throw failure('upstream_redirect');
      await save(); checkSignal(signal);
      res.writeHead(status, headersFor(upstreamResponse.headers, response.bytes));
      res.end(bytes(response)); counts.complete++;
    } catch (error) {
      if (signal.aborted) {
        try { checkSignal(signal); } catch (aborted) { error = aborted; }
      }
      if (!error.reason) error = failure('capture_write_failed');
      // Persist bounded partial bytes, but never promote a failed exchange.
      try { await save(error); } catch { counts.capture_write_failures++; }
      counts.failed++; replyError(res, error.status ?? 502);
    } finally {
      clearTimeout(timer); controllers.delete(control); res.off('close', disconnected);
      upstreamResponse?.destroy(); upstreamRequest?.destroy();
      // Drain only until the error response closes the connection; never forward a rejected body.
      if (!req.complete && !req.destroyed) req.resume();
    }
  }
  const server = http.createServer({ maxHeaderSize: 16_384 }, (req, res) => {
    const kind = req.method === 'POST' && req.url === '/v1/chat/completions' ? 'completion'
      : req.method === 'GET' && req.url === '/api/tags' ? 'metadata' : null;
    if (!kind) { rejected++; req.resume(); replyError(res, 404); return; }
    if (closing || accepted >= 10 || (kind === 'completion' && completions >= 2)) {
      rejected++; req.resume(); replyError(res, 429); return;
    }
    const sequence = ++accepted;
    if (kind === 'completion') completions++; // Reserve before the first await, never refund.
    const job = capture(req, res, sequence, kind);
    jobs.add(job); job.finally(() => jobs.delete(job)).catch(() => {});
  });
  server.on('connection', socket => { sockets.add(socket); socket.once('close', () => sockets.delete(socket)); });
  server.on('clientError', (_error, socket) => socket.destroy());
  await new Promise((ready, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', ready); });
  return { url: `http://127.0.0.1:${server.address().port}`,
    close() {
      closePromise ??= (async () => {
        closing = true;
        for (const controller of controllers) controller.abort('shutdown');
        const stopped = new Promise(resolveClose => server.close(resolveClose));
        for (const socket of sockets) socket.destroy();
        await Promise.allSettled([...jobs]); await stopped;
        const summary = { schema: 1, ended_at: stamp(), accepted, completions, rejected, ...counts };
        try {
          await writeFile(join(outputDir, 'summary.json'), JSON.stringify(summary, null, 2), { flag: 'wx' });
          return { ...summary, summaryWritten: true };
        } catch { return { ...summary, summaryWritten: false }; }
      })();
      return closePromise;
    } };
}

async function cli(args) {
  const options = {};
  for (let i = 0; i < args.length; i += 2) {
    const key = { '--upstream': 'upstream', '--out': 'outputDir', '--port': 'port' }[args[i]];
    if (!key || !args[i + 1] || key in options) throw Error('Use --upstream ORIGIN --out NEW_ABSOLUTE_DIR [--port PORT]');
    options[key] = key === 'port' ? Number(args[i + 1]) : args[i + 1];
  }
  const proxy = await createRecordingProxy(options);
  process.stdout.write(`${JSON.stringify({ url: proxy.url, upstream: options.upstream,
    outputDir: options.outputDir, inference_authorized: false })}\n`);
  const stop = async () => {
    const summary = await proxy.close();
    process.stdout.write(`${JSON.stringify(summary)}\n`);
    if (!summary.summaryWritten || summary.capture_write_failures) process.exitCode = 1;
  };
  process.once('SIGINT', stop); process.once('SIGTERM', stop);
}
if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  cli(process.argv.slice(2)).catch(error => { process.stderr.write(`${error.message}\n`); process.exitCode = 1; });
}
