import test from 'node:test';
import assert from 'node:assert/strict';
import { queryCrawlers, crawlerAnalytics, crawlers } from '../../academy/worker/crawlers.js';

const env = { CF_ACCOUNT_ID: 'account', ANALYTICS_API_TOKEN: 'private-token' };
const result = () => Response.json({ data: [{ crawler: 'Googlebot', surface: 'llms', requests: '42' }, { crawler: 'Googlebot', surface: 'pages', requests: 42 }] });
test('crawler query returns bounded aggregates with provenance and empty groups as zero', async () => {
  const data = await queryCrawlers(env, async (url, init) => {
    assert.equal(url, 'https://api.cloudflare.com/client/v4/accounts/account/analytics_engine/sql');
    assert.equal(init.headers.Authorization, 'Bearer private-token');
    assert.match(init.body, /SUM\(_sample_interval\)/);
    assert.match(init.body, /2026-11-15 00:00:00/);
    assert.match(init.body, /blob3 = '33audio-com.pages.dev'/);
    return result();
  }, new Date('2026-11-16T00:00:00Z'));
  assert.equal(data.kind, 'real');
  assert.deepEqual(data.rows[0], { label: 'Googlebot', llms: 42, pages: 42 });
  assert.equal(data.rows[1].pages, 0);
  assert.ok(!JSON.stringify(data).includes('private-token'));
});
test('HTTP errors and malformed results fail instead of showing zero; empty data is valid', async () => {
  for (const response of [new Response('', { status: 403 }), Response.json({ errors: [] }), Response.json({ data: [{ crawler: 'Googlebot', surface: 'llms', requests: 'bad' }] })]) {
    await assert.rejects(queryCrawlers(env, async () => response));
  }
  const empty = await queryCrawlers(env, async () => Response.json({ data: [] }));
  assert.ok(empty.rows.every(r => r.llms === 0 && r.pages === 0));
});
test('endpoint handles configuration, failures, normalized cache keys and cache hits', async () => {
  const ctx = { waitUntil(p) { this.pending = p; } };
  const request = new Request('https://academy.example/api/crawler-analytics?bypass=1');
  assert.equal((await (await crawlerAnalytics(request, {}, ctx)).json()).kind, 'unconfigured');
  assert.equal((await crawlerAnalytics(new Request(request, { method: 'POST' }), env, ctx)).status, 405);
  let stored;
  const cache = { match: async () => stored?.clone(), put: async (key, response) => { assert.equal(key.url, 'https://academy.example/api/crawler-analytics'); stored = response; } };
  const response = await crawlerAnalytics(request, env, ctx, cache, async () => result());
  await ctx.pending;
  assert.equal(response.headers.get('Cache-Control'), 'public, max-age=60');
  const hit = await crawlerAnalytics(request, env, ctx, cache, () => { throw Error('should not fetch'); });
  assert.equal((await hit.json()).kind, 'real');
  const failed = await crawlerAnalytics(request, env, ctx, { match: async () => null }, async () => { throw Error('private-token'); });
  assert.equal(failed.status, 502);
  assert.ok(!(await failed.text()).includes('private-token'));
});

import { onRequest } from '../../functions/_middleware.js';
import { crawlerEvent } from '../../worker/crawlers.js';
const request = (path, ua = 'Example GPTBot/1.0', host = '33audio-com.pages.dev', method = 'GET') => new Request(`https://${host}${path}`, { method, headers: { 'User-Agent': ua } });
test('middleware records crawler aggregates and preserves static responses', async () => {
  const response = new Response('static part', { headers: { ETag: 'original' } });
  const points = [];
  assert.equal(await onRequest({ request: request('/parts/mm177-1k/?private=query'), env: { CRAWLER_EVENTS: { writeDataPoint: p => points.push(p) } }, next: async () => response }), response);
  assert.deepEqual(points, [{ blobs: ['GPTBot', 'pages', '33audio-com.pages.dev'], doubles: [1], indexes: ['GPTBot'] }]);
  assert.equal(crawlerEvent(request('/llms.txt', 'claudebot/1.0'), response, '33audio-com.pages.dev').blobs[1], 'llms');
  for (const req of [request('/api/search'), request('/styles.css'), request('/llms.txt', 'Mozilla/5.0'), request('/llms.txt', 'GPTBot', 'preview.pages.dev'), request('/llms.txt', 'GPTBot', '33audio-com.pages.dev', 'POST')]) {
    assert.equal(crawlerEvent(req, response, '33audio-com.pages.dev'), null);
  }
  assert.equal(crawlerEvent(request('/llms.txt'), new Response('', { status: 404 }), '33audio-com.pages.dev'), null);
  assert.equal(await onRequest({ request: request('/llms.txt'), env: {}, next: async () => response }), response);
  assert.equal(await onRequest({ request: request('/llms.txt'), env: { CRAWLER_EVENTS: { writeDataPoint() { throw Error('failed'); } } }, next: async () => response }), response);
});
