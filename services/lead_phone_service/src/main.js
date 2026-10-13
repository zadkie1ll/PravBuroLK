import { Queue, createGatewayClient, createServer, sleep } from './service.js';

const log = entry => console.log(JSON.stringify({ time: new Date().toISOString(), ...entry }));
try {
  const secret = process.env.ENDPOINT_SECRET ?? '';
  if (!/^[a-zA-Z0-9_-]{32,}$/.test(secret)) throw new Error('configuration');
  const call = createGatewayClient(process.env.BITRIX_GATEWAY_BASE_URL ?? '', process.env.BITRIX_GATEWAY_TOKEN ?? '', process.env.BITRIX_GATEWAY_PROFILE ?? 'consultation');
  const queue = new Queue(process.env.QUEUE_FILE ?? './data/jobs.json');
  await queue.open();
  // Serialize file mutations and REST work; acknowledge only after durable enqueue.
  let chain = Promise.resolve();
  const serialize = fn => {
    const task = chain.then(fn); chain = task.catch(() => {}); return task;
  };
  const server = createServer(secret, id => serialize(() => queue.add(id)));
  const port = Number(process.env.PORT ?? 8013);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('configuration');
  server.listen(port, process.env.HOST ?? '127.0.0.1', () => log({ event: 'started', port }));
  server.on('error', () => { log({ event: 'server_failed' }); process.exit(1); });
  let running = true;
  for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => { running = false; server.close(); });
  while (running) {
    await serialize(() => queue.tick(call, log));
    await sleep(500);
  }
  await chain;
} catch {
  // Never print exception messages: fetch errors may contain webhook credentials.
  log({ event: 'startup_or_storage_failed' }); process.exit(1);
}
