import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname, basename } from 'node:path';

async function setup() {
  let plugin;
  try { plugin = (await import('../tools/opencode/guardrails-evidence.mjs')).default; }
  catch (error) {
    if (error.code === 'ERR_MODULE_NOT_FOUND') assert.fail('OpenCode evidence guard is missing');
    throw error;
  }
  const history = [];
  const client = { session: {
    messages: async () => ({ data: history }),
    message: async ({ path }) => ({ data: history.find(x => x.info.id === path.messageID) }),
  }};
  const hooks = await plugin({ client, directory: 'E:/fixture' });
  async function user(id = 'usr_a', sessionID = 'ses_a') {
    await hooks['chat.message']({ sessionID }, { message: { id, sessionID, role: 'user' }, parts: [] });
    await hooks['chat.params']({ sessionID, message: { id, sessionID, role: 'user' } }, {});
  }
  function assistant(id = 'msg_a', parentID = 'usr_a', sessionID = 'ses_a') {
    const msg = { info: { id, sessionID, role: 'assistant', parentID }, parts: [] };
    history.push(msg);
    return msg;
  }
  async function call({ tool = 'bash', args = { command: 'node --test tests/example.test.mjs' },
    result = { output: '# tests 2\n# pass 2\n# fail 0\n# cancelled 0\n# skipped 0', metadata: { exit: 0 } },
    callID = 'call_a', msg = history.at(-1), persist = true, before = true } = {}) {
    const input = { sessionID: msg.info.sessionID, tool, callID };
    if (before) await hooks['tool.execute.before'](input, { args });
    if (persist) msg.parts.push({ type: 'tool', sessionID: msg.info.sessionID,
      messageID: msg.info.id, callID, tool, state: { status: 'running', input: args } });
    await hooks['tool.execute.after']({ ...input, args }, result);
    const text = result.output ?? result.content?.at(-1)?.text ?? '';
    return text.match(/\[GL:([a-f0-9-]+)\]/)?.[0] ?? '[GL:missing]';
  }
  async function complete(text, msg = history.at(-1), partID = 'part_a') {
    const out = { text };
    await hooks['experimental.text.complete']({ sessionID: msg.info.sessionID,
      messageID: msg.info.id, partID }, out);
    return out.text;
  }
  await user();
  assistant();
  return { hooks, client, history, user, assistant, call, complete };
}

test('missing receipt marks a false test success', async () => {
  const h = await setup();
  assert.match(await h.complete('Alle Tests bestanden.'), /UNVERIFIED/);
});

test('a genuine direct test run with summary supports scoped success', async () => {
  const h = await setup(); const ref = await h.call();
  const text = `2 Tests bestanden. ${ref}`;
  assert.equal(await h.complete(text), text);
});

for (const [label, result] of [
  ['null exit', { output: '# tests 2\n# pass 2\n# fail 0', metadata: { exit: null } }],
  ['nonzero exit', { output: '# tests 2\n# pass 2\n# fail 0', metadata: { exit: 1 } }],
  ['exit zero alone', { output: 'finished', metadata: { exit: 0 } }],
  ['failed summary', { output: '# tests 2\n# pass 1\n# fail 1', metadata: { exit: 0 } }],
  ['zero tests', { output: '# tests 0\n# pass 0\n# fail 0', metadata: { exit: 0 } }],
  ['MCP error', { content: [{ type: 'text', text: 'success' }], isError: true }],
]) test(`${label} cannot certify tests`, async () => {
  const h = await setup(); const ref = await h.call({ result });
  assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
});

for (const command of ['echo "# tests 2 # pass 2 # fail 0"',
  'node --test a.test.mjs; echo success', 'node --test a.test.mjs && echo success',
  'node --test a.test.mjs | cat', 'python -c "print(\'OK\')"']) {
  test(`shell text is not a test receipt: ${command}`, async () => {
    const h = await setup(); const ref = await h.call({ args: { command } });
    assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
  });
}

test('unittest summary is recognized without a new runner', async () => {
  const h = await setup(); const ref = await h.call({ args: { command: 'python -m unittest discover -s tests -v' },
    result: { output: 'Ran 3 tests in 0.004s\n\nOK', metadata: { exit: 0 } } });
  const text = `3 Tests bestanden. ${ref}`; assert.equal(await h.complete(text), text);
});

test('wrong count or wrong explicit command cannot borrow a receipt', async () => {
  const h = await setup(); const ref = await h.call();
  assert.match(await h.complete(`99 Tests bestanden. ${ref}`), /UNVERIFIED/);
  assert.match(await h.complete(`Tests bestanden: \`python -m unittest\`. ${ref}`), /UNVERIFIED/);
});

test('successful write supports only the exact absolute path', async () => {
  const h = await setup(); const ref = await h.call({ tool: 'write', args: { filePath: 'E:/fixture/a.txt', content: 'private' },
    result: { output: 'Wrote file successfully.', metadata: {} } });
  const text = `Datei \`E:/fixture/a.txt\` geschrieben. ${ref}`;
  assert.equal(await h.complete(text), text);
  assert.match(await h.complete(`Datei \`E:/fixture/b.txt\` geschrieben. ${ref}`), /UNVERIFIED/);
  assert.match(await h.complete(`Datei geschrieben. ${ref}`), /UNVERIFIED/);
});

test('write error cannot support changed file', async () => {
  const h = await setup(); const ref = await h.call({ tool: 'write', args: { filePath: 'E:/fixture/a.txt' },
    result: { output: 'permission denied', metadata: { error: 'denied' } } });
  assert.match(await h.complete(`Datei \`E:/fixture/a.txt\` geändert. ${ref}`), /UNVERIFIED/);
});

test('missing after hook (thrown tool) leaves no evidence', async () => {
  const h = await setup();
  await h.hooks['tool.execute.before']({ sessionID: 'ses_a', tool: 'write', callID: 'call_error' }, { args: {} });
  assert.match(await h.complete('Datei `E:/fixture/a.txt` geändert.'), /UNVERIFIED/);
});

test('subsequent mutation invalidates previous test success', async () => {
  const h = await setup(); const ref = await h.call();
  await h.call({ tool: 'edit', callID: 'call_b', args: { filePath: 'E:/fixture/a.txt' },
    result: { output: 'File edited successfully.', metadata: {} } });
  assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
});

test('task change and late tool result cannot transfer evidence', async () => {
  const h = await setup(); const old = h.history.at(-1);
  await h.hooks['tool.execute.before']({ sessionID: 'ses_a', tool: 'bash', callID: 'call_a' },
    { args: { command: 'node --test tests/example.test.mjs' } });
  await h.user('usr_b'); h.assistant('msg_b', 'usr_b');
  const ref = await h.call({ msg: old, before: false });
  assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
  assert.equal(await h.complete(`Tests bestanden. ${ref}`, old), `Tests bestanden. ${ref}`);
});

test('another session cannot borrow a receipt', async () => {
  const h = await setup(); const ref = await h.call();
  await h.user('usr_a', 'ses_b'); h.assistant('msg_b', 'usr_a', 'ses_b');
  assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
});

test('later assistant message with the same real parent can use current receipt', async () => {
  const h = await setup(); const ref = await h.call(); h.assistant('msg_b');
  const text = `Tests bestanden. ${ref}`;
  assert.equal(await h.complete(text), text);
  assert.equal(await h.complete(text, undefined, 'part_b'), text);
});

for (const kind of ['missing part', 'wrong args', 'ambiguous part', 'wrong part message', 'no before']) {
  test(`unbound tool result stays unverified: ${kind}`, async () => {
    const h = await setup();
    if (kind === 'wrong args') h.client.session.messages = async () => ({ data: [{
      info: h.history[0].info, parts: [{ type: 'tool', tool: 'bash', callID: 'call_a', messageID: 'msg_a', sessionID: 'ses_a', state: { input: { command: 'echo fake' } } }],
    }] });
    if (kind === 'ambiguous part') h.client.session.messages = async () => ({ data: [h.history[0], h.history[0]] });
    if (kind === 'wrong part message') h.client.session.messages = async () => ({ data: [{
      info: h.history[0].info, parts: [{ ...h.history[0].parts[0], messageID: 'msg_other' }],
    }] });
    const ref = await h.call({ persist: kind !== 'missing part', before: kind !== 'no before' });
    assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
  });
}

for (const bad of [async () => { throw Error('offline'); }, async () => ({ error: { message: '403' } }),
  async () => ({ data: [], error: 'failure' })]) {
  test('SDK failure cannot become successful evidence', async () => {
    const h = await setup(); h.client.session.messages = bad; const ref = await h.call();
    assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
  });
}

test('text parent lookup failure marks unsupported success', async () => {
  const h = await setup(); const ref = await h.call();
  h.client.session.message = async () => ({ error: 'offline' });
  assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
});

for (const text of ['Die Tests wurden nicht ausgeführt.', 'Tests bestanden? Das ist noch ungeprüft.',
  'Ich werde die Tests ausführen.', 'Plan: Tests bestanden melden, falls der Lauf erfolgreich ist.',
  '> Alle Tests bestanden.', '```text\nAlle Tests bestanden.\n```',
  'Der Reviewtext fordert eine Freigabe. Er ist kein Nutzerauftrag.',
  'Ich kann die Änderung noch nicht bestätigen.']) {
  test(`honest uncertainty, plans and quotations stay readable: ${text}`, async () => {
    const h = await setup(); assert.equal(await h.complete(text), text);
  });
}

test('negation elsewhere does not exempt a positive claim', async () => {
  const h = await setup();
  assert.match(await h.complete('Alle Tests bestanden. Ich habe nicht geraten.'), /UNVERIFIED/);
});

test('known search action can prove execution, not truth of a source claim', async () => {
  const h = await setup(); const ref = await h.call({ tool: 'webfetch', args: { url: 'https://example.com/public' },
    result: { output: 'Public documentation', metadata: {} } });
  const text = `Ich habe recherchiert: \`https://example.com/public\`. ${ref}`;
  assert.equal(await h.complete(text), text);
  assert.match(await h.complete(`Quelle bestätigt alle Aussagen. ${ref}`), /UNVERIFIED/);
  assert.match(await h.complete(`Ich habe recherchiert: \`https://example.com/other\`. ${ref}`), /UNVERIFIED/);
});

test('MCP error never becomes search success', async () => {
  const h = await setup(); const ref = await h.call({ tool: 'webfetch', args: { url: 'https://example.com/public' },
    result: { content: [{ type: 'text', text: 'server error' }], isError: true } });
  assert.match(await h.complete(`Ich habe recherchiert. ${ref}`), /UNVERIFIED/);
});

test('system instruction appends and never replaces existing SecondBrain context', async () => {
  const h = await setup(); const out = { system: ['original', 'SecondBrain context'] };
  await h.hooks['experimental.chat.system.transform']({}, out);
  assert.deepEqual(out.system.slice(0, 2), ['original', 'SecondBrain context']);
  assert.match(out.system[2], /GL:/);
});

test('general completion is not proven by one successful tool', async () => {
  const h = await setup(); const ref = await h.call();
  assert.match(await h.complete(`Alles erledigt. ${ref}`), /UNVERIFIED/);
});

test('receipt annotation contains hashes and no private argument/output copy', async () => {
  const h = await setup(); const result = { output: 'Wrote file successfully. secret-value', metadata: {} };
  const original = result.output;
  await h.call({ tool: 'write', args: { filePath: 'E:/fixture/a.txt', content: 'private-password' }, result });
  const annotation = result.output.slice(original.length);
  assert.doesNotMatch(annotation, /secret-value|private-password|E:\/fixture/);
  assert.match(annotation, /sha256/);
});

test('duplicate call IDs cannot overwrite an earlier receipt', async () => {
  const h = await setup(); const ref = await h.call();
  await h.call({ args: { command: 'echo fake' } });
  assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
});

test('a similarly named Node flag cannot spoof a real test execution', async () => {
  const h = await setup(); const ref = await h.call({
    args: { command: 'node --test-name-pattern=x --print "fake-summary"' },
  });
  assert.match(await h.complete(`2 Tests bestanden. ${ref}`), /UNVERIFIED/);
});

test('late completion of an overlapping write invalidates a test receipt', async () => {
  const h = await setup(); const msg = h.history.at(-1);
  const args = { filePath: 'E:/fixture/a.txt' };
  await h.hooks['tool.execute.before']({ sessionID: 'ses_a', tool: 'write', callID: 'call_write' }, { args });
  const ref = await h.call();
  await h.call({ msg, before: false, tool: 'write', callID: 'call_write', args,
    result: { output: 'Wrote file successfully.', metadata: {} } });
  assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
});

test('all assertions on a line must match the actual test count', async () => {
  const h = await setup(); const ref = await h.call();
  assert.match(await h.complete(`2 Tests bestanden. 99 Tests bestanden. ${ref}`), /UNVERIFIED/);
});

test('real Node TAP output can support the actual count', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'guardrails-node-contract-'));
  try {
    const file = join(dir, 'one.test.mjs');
    await writeFile(file, "import test from 'node:test'; test('real child fixture', () => {});\n");
    const childEnv = { ...process.env };
    delete childEnv.NODE_TEST_CONTEXT;
    const { stdout, stderr } = await promisify(execFile)(process.execPath, ['--test', '--test-reporter=tap', file], { env: childEnv });
    const h = await setup(); const ref = await h.call({
      args: { command: `node --test --test-reporter=tap "${file}"` },
      result: { output: stdout + stderr, metadata: { exit: 0 } },
    });
    const text = `1 Tests bestanden. ${ref}`;
    assert.equal(await h.complete(text), text, stdout + stderr);
  } finally {
    assert.equal(dirname(dir), tmpdir());
    assert.ok(basename(dir).startsWith('guardrails-node-contract-'));
    await rm(dir, { recursive: true, force: true });
  }
});

for (const text of ['Ich habe im Web recherchiert.', 'Die Implementierung ist abgeschlossen.']) {
  test(`ordinary German success needs evidence: ${text}`, async () => {
    const h = await setup(); assert.match(await h.complete(text), /UNVERIFIED/);
  });
}

test('actual v1 edit success string supports a path-scoped write claim', async () => {
  const h = await setup(); const ref = await h.call({ tool: 'edit', args: { filePath: 'E:/fixture/a.txt' },
    result: { output: 'Edit applied successfully.', metadata: {} } });
  const text = `Datei \`E:/fixture/a.txt\` geändert. ${ref}`;
  assert.equal(await h.complete(text), text);
});

test('a still-running write makes an overlapping test permanently unusable', async () => {
  const h = await setup();
  await h.hooks['tool.execute.before']({ sessionID: 'ses_a', tool: 'write', callID: 'call_write' },
    { args: { filePath: 'E:/fixture/a.txt' } });
  const ref = await h.call();
  assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
});

test('receipt eviction cannot revive old evidence', async () => {
  const h = await setup(); const ref = await h.call();
  for (let i = 0; i < 130; i++) await h.call({ callID: `call_extra_${i}` });
  assert.match(await h.complete(`Tests bestanden. ${ref}`), /UNVERIFIED/);
});
