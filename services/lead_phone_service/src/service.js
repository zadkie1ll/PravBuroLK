import http from 'node:http';
import { timingSafeEqual } from 'node:crypto';
import { mkdir, readFile, open, rename } from 'node:fs/promises';
import { dirname } from 'node:path';

export const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
export class ServiceError extends Error {
  constructor(code, retryable = false) {
    super(code); this.code = code; this.retryable = retryable;
  }
}

export function phoneChanges(item) {
  if (!item || (item.fm != null && !Array.isArray(item.fm))) {
    throw new ServiceError('INVALID_ITEM');
  }
  const changes = {};
  for (const field of item.fm ?? []) {
    if (field.typeId !== 'PHONE' || field.valueType !== 'OTHER') continue;
    // Never send a missing/empty value: Bitrix interprets it as deletion.
    if (!/^[1-9]\d*$/.test(String(field.id)) ||
        typeof field.value !== 'string' || !field.value.trim()) {
      throw new ServiceError('INVALID_PHONE_RECORD');
    }
    changes[String(field.id)] = {
      typeId: 'PHONE', valueType: 'WORK', value: field.value,
    };
  }
  return changes;
}

export function createClient(baseUrl, { fetchImpl = fetch, wait = sleep } = {}) {
  const base = new URL(baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`);
  if (base.protocol !== 'https:' || !/^\/rest\/\d+\/[^/]+\/$/.test(base.pathname) ||
      base.username || base.password || base.search || base.hash) {
    throw new ServiceError('INVALID_WEBHOOK_URL');
  }
  return async (method, params) => {
    for (let attempt = 0; attempt < 4; attempt++) {
      try {
        const response = await fetchImpl(new URL(`${method}.json`, base), {
          method: 'POST', redirect: 'error',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params), signal: AbortSignal.timeout(15000),
        });
        let payload;
        try { payload = await response.json(); }
        catch { throw new ServiceError('INVALID_REST_RESPONSE', true); }
        if (!response.ok || payload.error) {
          const retryable = response.status === 429 || response.status >= 500 ||
            ['QUERY_LIMIT_EXCEEDED', 'OPERATION_TIME_LIMIT'].includes(payload.error);
          throw new ServiceError(retryable ? 'REST_TEMPORARY_ERROR' : 'REST_REJECTED', retryable);
        }
        if (!payload.result) throw new ServiceError('INVALID_REST_RESPONSE', true);
        return payload.result;
      } catch (error) {
        const safe = error instanceof ServiceError ? error : new ServiceError('REST_NETWORK_ERROR', true);
        // An ambiguous update must be retried by the job, after reading the lead again.
        if (method === 'crm.item.update' || !safe.retryable || attempt === 3) throw safe;
        await wait(1000 * 2 ** attempt);
      }
    }
  };
}

export function createGatewayClient(baseUrl, token, profile = 'consultation', { fetchImpl = fetch, wait = sleep } = {}) {
  const base = new URL(baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`);
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash || !token) {
    throw new ServiceError('INVALID_GATEWAY_CONFIG');
  }
  return async (method, params) => {
    for (let attempt = 0; attempt < 4; attempt++) {
      try {
        const response = await fetchImpl(new URL('bitrix/call', base), {
          method: 'POST', redirect: 'error',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ profile, method, params }), signal: AbortSignal.timeout(15000),
        });
        let payload;
        try { payload = await response.json(); }
        catch { throw new ServiceError('INVALID_GATEWAY_RESPONSE', true); }
        if (!response.ok || payload.detail || !Object.hasOwn(payload, 'result')) {
          throw new ServiceError(response.status >= 500 ? 'GATEWAY_TEMPORARY_ERROR' : 'GATEWAY_REJECTED', response.status >= 500);
        }
        return payload.result;
      } catch (error) {
        const safe = error instanceof ServiceError ? error : new ServiceError('GATEWAY_NETWORK_ERROR', true);
        if (method === 'crm.item.update' || !safe.retryable || attempt === 3) throw safe;
        await wait(1000 * 2 ** attempt);
      }
    }
  };
}

export async function processLead(call, id) {
  const result = await call('crm.item.get', { entityTypeId: 1, id: Number(id) });
  const item = result.item;
  const fm = phoneChanges(item);
  if (!(item.fm ?? []).some(field => field.typeId === 'PHONE')) {
    throw new ServiceError('PHONE_NOT_READY', true);
  }
  if (Object.keys(fm).length) {
    await call('crm.item.update', { entityTypeId: 1, id: Number(id), fields: { fm } });
  }
  return Object.keys(fm).length;
}

// One process/replica owns this file. Only IDs and job metadata are persisted.
export class Queue {
  constructor(path, { now = Date.now } = {}) { this.path = path; this.now = now; this.jobs = {}; }
  async open() {
    await mkdir(dirname(this.path), { recursive: true });
    try { this.jobs = JSON.parse(await readFile(this.path, 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  async save() {
    const file = await open(`${this.path}.tmp`, 'w', 0o600);
    try { await file.writeFile(JSON.stringify(this.jobs)); await file.sync(); }
    finally { await file.close(); }
    await rename(`${this.path}.tmp`, this.path);
    const directory = await open(dirname(this.path), 'r');
    try { await directory.sync(); } finally { await directory.close(); }
  }
  async add(id) {
    if (this.jobs[id]) return false;
    this.jobs[id] = { status: 'pending', attempts: 0, nextAt: this.now() };
    try { await this.save(); } catch (error) { delete this.jobs[id]; throw error; }
    return true;
  }
  async tick(call, log) {
    const entry = Object.entries(this.jobs).find(([, job]) => job.status === 'pending' && job.nextAt <= this.now());
    if (!entry) return;
    const [id, job] = entry;
    try {
      const changed = await processLead(call, id);
      job.status = 'done'; log({ event: 'lead_processed', leadId: id, changed });
    } catch (error) {
      job.attempts++;
      const retry = error.retryable && job.attempts < 8;
      job.status = retry ? 'pending' : 'failed';
      job.nextAt = this.now() + Math.min(300000, 2000 * 2 ** (job.attempts - 1));
      log({ event: retry ? 'lead_retry' : 'lead_failed', leadId: id,
        code: error instanceof ServiceError ? error.code : 'PROCESSING_ERROR', attempts: job.attempts });
    }
    await this.save();
  }
}

export function eventId(body) {
  const id = body?.data?.FIELDS?.ID ?? body?.['data[FIELDS][ID]'];
  return /^[1-9]\d*$/.test(String(id)) && Number.isSafeInteger(Number(id)) ? String(id) : null;
}

export function createServer(secret, enqueue) {
  const reply = (res, status, body) => {
    res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body));
  };
  const server = http.createServer(async (req, res) => {
    if (req.method === 'GET' && req.url === '/health') return reply(res, 200, { status: 'ok' });
    const match = /^\/webhooks\/bitrix24\/([^/?]+)$/.exec(req.url ?? '');
    if (req.method !== 'POST' || !match) return reply(res, 404, { error: 'not_found' });
    const provided = Buffer.from(match[1]); const expected = Buffer.from(secret);
    if (provided.length !== expected.length || !timingSafeEqual(provided, expected)) {
      return reply(res, 403, { error: 'forbidden' });
    }
    try {
      let size = 0; const chunks = [];
      for await (const chunk of req) {
        size += chunk.length;
        if (size > 65536) { reply(res, 413, { error: 'too_large' }); req.destroy(); return; }
        chunks.push(chunk);
      }
      const text = Buffer.concat(chunks).toString('utf8');
      const type = (req.headers['content-type'] ?? '').split(';')[0].trim();
      if (!['application/json', 'application/x-www-form-urlencoded'].includes(type)) {
        return reply(res, 415, { error: 'unsupported_content_type' });
      }
      let body;
      try { body = type === 'application/json' ? JSON.parse(text) : Object.fromEntries(new URLSearchParams(text)); }
      catch { return reply(res, 400, { error: 'invalid_body' }); }
      if (body?.event !== 'ONCRMLEADADD') return reply(res, 200, { status: 'ignored' });
      const id = eventId(body);
      if (!id) return reply(res, 400, { error: 'invalid_lead_id' });
      await enqueue(id);
      reply(res, 202, { status: 'accepted' });
    } catch { reply(res, 503, { error: 'queue_unavailable' }); }
  });
  server.requestTimeout = 20000;
  return server;
}
