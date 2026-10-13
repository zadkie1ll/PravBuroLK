import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Queue, ServiceError, createClient, createGatewayClient, createServer, eventId, phoneChanges, processLead } from '../src/service.js';

const phone = (id, valueType = 'OTHER') => ({ id, typeId: 'PHONE', valueType, value: `+7000000000${id}` });

test('multiple phones: only OTHER changes, existing IDs and values retained', async () => {
  const item = { fm: [phone(1), phone(2, 'WORK'), phone(3, 'MOBILE'), phone(4),
    { id: 5, typeId: 'EMAIL', valueType: 'OTHER', value: 'a@example.org' }] };
  const original = structuredClone(item); const calls = [];
  const count = await processLead(async (method, params) => {
    calls.push({ method, params }); return { item };
  }, '17');
  assert.equal(count, 2);
  assert.deepEqual(calls[1], { method: 'crm.item.update', params: {
    entityTypeId: 1, id: 17, fields: { fm: {
      1: { typeId: 'PHONE', valueType: 'WORK', value: phone(1).value },
      4: { typeId: 'PHONE', valueType: 'WORK', value: phone(4).value },
    } },
  } });
  assert.deepEqual(item, original);
});

test('already WORK: no update; replay stays idempotent', async () => {
  const item = { fm: [phone(1)] }; let updates = 0;
  const call = async method => {
    if (method === 'crm.item.update') { updates++; item.fm[0].valueType = 'WORK'; }
    return { item };
  };
  await processLead(call, '17'); await processLead(call, '17');
  assert.equal(updates, 1);
});

test('no phone retries; invalid ID or empty value fails without deletion/addition', async () => {
  await assert.rejects(processLead(async () => ({ item: { fm: [] } }), '17'), { code: 'PHONE_NOT_READY' });
  assert.throws(() => phoneChanges({ fm: [{ ...phone(1), id: undefined }] }), { code: 'INVALID_PHONE_RECORD' });
  assert.throws(() => phoneChanges({ fm: [{ ...phone(1), value: '' }] }), { code: 'INVALID_PHONE_RECORD' });
  assert.throws(() => phoneChanges({ fm: {} }), { code: 'INVALID_ITEM' });
});

test('ID parsing supports JSON and flattened form', () => {
  assert.equal(eventId({ data: { FIELDS: { ID: '17' } } }), '17');
  assert.equal(eventId({ 'data[FIELDS][ID]': '17' }), '17');
  for (const id of ['0', '-1', '1.1', 'bad', '9007199254740992']) assert.equal(eventId({ 'data[FIELDS][ID]': id }), null);
});

test('queue survives restart, deduplicates, retries missing phones', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'lead-phone-test-'));
  try {
    let now = 1000;
    const queue = new Queue(join(dir, 'jobs.json'), { now: () => now }); await queue.open();
    assert.equal(await queue.add('17'), true); assert.equal(await queue.add('17'), false);
    await queue.tick(async () => ({ item: { fm: [] } }), () => {});
    assert.equal(queue.jobs['17'].status, 'pending');
    now += 2000;
    const restarted = new Queue(queue.path, { now: () => now }); await restarted.open();
    await restarted.tick(async () => ({ item: { fm: [phone(1, 'WORK')] } }), () => {});
    assert.equal(restarted.jobs['17'].status, 'done'); assert.equal(await restarted.add('17'), false);
  } finally { await rm(dir, { recursive: true }); }
});

test('permanent errors fail; transient retries exhaust safely', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'lead-phone-test-'));
  try {
    let now = 0; const queue = new Queue(join(dir, 'jobs.json'), { now: () => now }); await queue.open();
    await queue.add('1');
    await queue.tick(async () => { throw new ServiceError('REST_REJECTED'); }, () => {});
    assert.equal(queue.jobs['1'].status, 'failed');
    await queue.add('2');
    for (let i = 0; i < 8; i++) {
      await queue.tick(async () => { throw new ServiceError('REST_NETWORK_ERROR', true); }, () => {});
      now += 300000;
    }
    assert.equal(queue.jobs['2'].status, 'failed');
  } finally { await rm(dir, { recursive: true }); }
});

test('REST limits retry reads; auth errors never leak secrets', async () => {
  let attempts = 0;
  const call = createClient('https://example.bitrix24.ru/rest/1/secret/', {
    wait: async () => {}, fetchImpl: async () => {
      attempts++; return attempts === 1 ? new Response(JSON.stringify({ error: 'QUERY_LIMIT_EXCEEDED' }), { status: 429 })
        : new Response(JSON.stringify({ result: { item: { fm: [] } } }));
    },
  });
  await call('crm.item.get', {}); assert.equal(attempts, 2);
  const rejected = createClient('https://example.bitrix24.ru/rest/1/secret/', {
    fetchImpl: async () => new Response(JSON.stringify({ error: 'INVALID_CREDENTIALS', error_description: 'secret' }), { status: 401 }),
  });
  await assert.rejects(rejected('crm.item.get', {}), { message: 'REST_REJECTED', retryable: false });
});

test('ambiguous update never blindly retries the same payload', async () => {
  let requests = 0;
  const call = createClient('https://example.bitrix24.ru/rest/1/secret/', {
    fetchImpl: async () => { requests++; throw new Error('secret URL'); },
  });
  await assert.rejects(call('crm.item.update', {}), { code: 'REST_NETWORK_ERROR' });
  assert.equal(requests, 1);
});

test('gateway client uses internal token and consultation profile', async () => {
  let request;
  const call = createGatewayClient('http://127.0.0.1:8002', 'internal-token', 'consultation', {
    fetchImpl: async (url, options) => { request = { url: String(url), options }; return new Response(JSON.stringify({ result: { item: { fm: [] } } })); },
  });
  await call('crm.item.get', { entityTypeId: 1, id: 17 });
  assert.equal(request.url, 'http://127.0.0.1:8002/bitrix/call');
  assert.equal(request.options.headers.Authorization, 'Bearer internal-token');
  assert.deepEqual(JSON.parse(request.options.body), { profile: 'consultation', method: 'crm.item.get', params: { entityTypeId: 1, id: 17 } });
});

test('HTTP secret, event filtering, JSON and form, invalid payload', async () => {
  const secret = 'a'.repeat(32); const ids = [];
  const server = createServer(secret, async id => ids.push(id));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const url = `http://127.0.0.1:${server.address().port}/webhooks/bitrix24/`;
    const send = (suffix, body, type = 'application/json') => fetch(url + suffix, {
      method: 'POST', headers: { 'Content-Type': type }, body,
    });
    assert.equal((await send('wrong', '{}')).status, 403);
    assert.equal((await send(secret, JSON.stringify({ event: 'ONCRMLEADUPDATE' }))).status, 200);
    assert.equal((await send(secret, '{')).status, 400);
    assert.equal((await send(secret, JSON.stringify({ event: 'ONCRMLEADADD' }))).status, 400);
    assert.equal((await send(secret, JSON.stringify({ event: 'ONCRMLEADADD', data: { FIELDS: { ID: 17 } } }))).status, 202);
    assert.equal((await send(secret, 'event=ONCRMLEADADD&data%5BFIELDS%5D%5BID%5D=18', 'application/x-www-form-urlencoded')).status, 202);
    assert.deepEqual(ids, ['17', '18']);
  } finally { await new Promise(resolve => server.close(resolve)); }
});
