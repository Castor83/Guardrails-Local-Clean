// Process-local network guard for this fixed offline regression CLI, not an OS sandbox.
'use strict';
const deny = () => { throw new Error('Offline Promptfoo regression: network is disabled'); };
require('node:net').Socket.prototype.connect = deny;
for (const name of ['node:http', 'node:https']) {
  const transport = require(name);
  transport.request = deny;
  transport.get = deny;
}
globalThis.fetch = async () => deny();
