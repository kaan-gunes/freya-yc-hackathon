import assert from 'node:assert/strict';
import { test } from 'node:test';
import fixtures from './test-customers.json' with { type: 'json' };
import worker from './worker.js';

const remote = process.env.MOCK_BASE_URL;
const request = (service, data) => new Request((remote || 'https://mock.example') + '/voice/v1/' + service, {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ data, call: { lang: 'tr' } }),
});
const send = request => remote ? fetch(request) : worker.fetch(request);
function payload(customer, card, week) {
  card = card || customer.services['cards.list']?.response.data?.cards?.[0]?.cardNumber
    || Object.keys(customer.services['cards.balance'] || {})[0] || 'synthetic-missing-card';
  const balance = customer.services['cards.balance']?.[card]?.response.data;
  const current = customer.services['statement.week.get']?.[card]?.response.data;
  return {
    customerNo: customer.customerNo, cardNumber: card, aiFlow: 'CardOps',
    newStatementWeek: week, statementDay: current?.statementDay || 1,
    intAddressInfoType: 'E', currencyType: 'TL',
    statementDate: balance?.statementDate || '05.10.2026',
    emailAddress: customer.services['contact.email.get']?.response.data?.ibanEmail || 'synthetic@freyabank.example',
  };
}

test('every supplied service response preserves its HTTP status, body and delay', async () => {
  let count = 0;
  const cases = [];
  for (const customer of fixtures.customers) {
    for (const [service, value] of Object.entries(customer.services)) {
      const calls = Object.hasOwn(value, 'http') ? [[undefined, undefined, value]]
        : Object.entries(value).flatMap(([card, cardValue]) => Object.hasOwn(cardValue, 'http') ? [[card, undefined, cardValue]]
          : Object.entries(cardValue).map(([week, leaf]) => [card, week, leaf]));
      for (const [card, week, expected] of calls) {
        cases.push(async () => {
          const label = customer.customerNo + ' ' + service + ' ' + (card || '') + ' ' + (week || '');
          const started = performance.now();
          const response = await send(request(service, payload(customer, card, week)));
          assert.equal(response.status, expected.http, label);
          assert.deepEqual(await response.json(), expected.response, label);
          if (expected.delaySeconds) assert.ok(performance.now() - started >= expected.delaySeconds * 1000 - 50, label + ' delay');
          count++;
        });
      }
    }
  }
  for (let start = 0; start < cases.length; start += 12) await Promise.all(cases.slice(start, start + 12).map(run => run()));
  assert.equal(count, 617);
});

test('number/string selector types are accepted and unknown keys use sourced errors', async () => {
  const expected = fixtures.customers[0].services['cards.list'];
  const response = await send(request('cards.list', { customerNo: Number(fixtures.customers[0].customerNo) }));
  assert.equal(response.status, expected.http);
  assert.deepEqual(await response.json(), expected.response);
  const card = Object.keys(fixtures.customers[0].services['statement.week.decide'])[0];
  const changed = await send(request('statement.week.decide', payload(fixtures.customers[0], card, 2)));
  assert.deepEqual(await changed.json(), fixtures.customers[0].services['statement.week.decide'][card]['2'].response);
  for (const [service, code, status] of [
    ['cards.list', 'FB_IVR_CHANNEL_102', 404], ['cards.balance', 'FB_IVR_CHANNEL_120', 404],
    ['statement.week.get', 'FB_IVR_CHANNEL_121', 404], ['statement.pdf.send', 'FB_IVR_CHANNEL_107', 404],
    ['statement.week.decide', 'INVALID_ARGUMENTS_ERROR', 400], ['statement.week.change', 'INVALID_ARGUMENTS_ERROR', 400],
    ['contact.email.get', 'INVALID_ARGUMENTS_ERROR', 400],
  ]) {
    const response = await send(request(service, { ...payload(fixtures.customers[0], 'unknown', 0), customerNo: 'unknown' }));
    assert.equal(response.status, status, service);
    const result = await response.json();
    assert.equal(result.result.returnCode, code, service);
    assert.equal(result.result.code, code, service);
    assert.equal(Object.hasOwn(result, 'data'), false, service);
  }
});

test('invalid requests cannot silently return a fixture', async () => {
  for (const service of Object.keys(fixtures.customers[0].services)) {
    const response = await send(request(service, {}));
    assert.equal(response.status, 400, service);
    assert.equal((await response.json()).result.code, 'INVALID_ARGUMENTS_ERROR', service);
  }
  const malformed = new Request((remote || 'https://mock.example') + '/voice/v1/cards.list', { method: 'POST', body: '{' });
  assert.equal((await send(malformed)).status, 400);
  assert.equal((await send(new Request((remote || 'https://mock.example') + '/voice/v1/cards.list'))).status, 405);
  assert.equal((await send(request('invented.service', {}))).status, 404);
  const customer = fixtures.customers[0];
  const card = Object.keys(customer.services['statement.week.decide'])[0];
  assert.equal((await send(request('statement.week.decide', payload(customer, card, '__proto__')))).status, 400);
  assert.equal((await send(request('statement.pdf.send', payload(customer, 'unknown-card')))).status, 404);
});
