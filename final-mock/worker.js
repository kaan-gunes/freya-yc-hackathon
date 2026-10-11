import fixtures from './test-customers.json' with { type: 'json' };

// Case-specific mock data stays separate from the generic builder.
const customers = new Map(fixtures.customers.map(customer => [String(customer.customerNo), customer]));
const services = {
  'cards.list': ['customerNo'],
  'cards.balance': ['cardNumber'],
  'statement.week.get': ['cardNumber'],
  'statement.week.decide': ['cardNumber', 'newStatementWeek', 'statementDay'],
  'statement.week.change': ['cardNumber', 'newStatementWeek', 'statementDay'],
  'contact.email.get': ['customerNo', 'intAddressInfoType'],
  'statement.pdf.send': ['customerNo', 'cardNumber', 'currencyType', 'statementDate', 'emailAddress'],
};
const cards = new Map();
for (const customer of fixtures.customers) {
  for (const service of ['cards.balance', 'statement.week.get', 'statement.week.decide', 'statement.week.change']) {
    for (const [card, value] of Object.entries(customer.services[service] || {})) {
      if (!cards.has(service)) cards.set(service, new Map());
      if (cards.get(service).has(card)) throw new Error('Duplicate card/service fixture');
      cards.get(service).set(card, value);
    }
  }
}
const headers = { 'content-type': 'application/json; charset=utf-8', 'access-control-allow-origin': '*' };
function json(value, status = 200) {
  return new Response(JSON.stringify(value), { status, headers });
}
function error(status, code, message, type = 'ERROR') {
  const guid = crypto.randomUUID();
  return json({ result: {
    guid, returnCode: code, messageText: message, code, message, type,
    details: { guid, rootCause: status === 404 ? 'NotFoundException' : 'InvalidArgumentsException', errorOrigin: 'core-freya-final' },
  } }, status);
}
function notFound(service) {
  const missing = {
    'cards.list': ['FB_IVR_CHANNEL_102', 'Müşteriye ait geçerli kart bilgisi bulunamadı.'],
    'cards.balance': ['FB_IVR_CHANNEL_120', 'Kart bakiye servisi hatası: kart bulunamadı'],
    'statement.week.get': ['FB_IVR_CHANNEL_121', 'Card not found'],
    'statement.pdf.send': ['FB_IVR_CHANNEL_107', 'Pdf dokümanı bulunamadı'],
  }[service];
  return missing ? error(404, missing[0], missing[1], 'WARNING')
    : error(400, 'INVALID_ARGUMENTS_ERROR', 'Requested test record not found');
}

export default {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: { ...headers, 'access-control-allow-methods': 'GET, POST, OPTIONS', 'access-control-allow-headers': '*' } });
    }
    if (request.method === 'GET' && path === '/health') return json({ status: 'ok', customers: customers.size });
    const service = path.startsWith('/voice/v1/') ? path.slice('/voice/v1/'.length) : '';
    if (!Object.hasOwn(services, service)) return json({ error: 'Unknown service' }, 404);
    if (request.method !== 'POST') return json({ error: 'POST required' }, 405);
    let body;
    try { body = await request.json(); } catch { return error(400, 'INVALID_ARGUMENTS_ERROR', 'JSON body is required'); }
    const data = body?.data;
    if (!data || typeof data !== 'object' || Array.isArray(data)) return error(400, 'INVALID_ARGUMENTS_ERROR', 'data cannot be empty');
    const missing = services[service].find(field => data[field] === undefined || data[field] === null || data[field] === '');
    if (missing) return error(400, 'INVALID_ARGUMENTS_ERROR', missing + ' cannot be empty');
    let record;
    if (service === 'cards.list' || service === 'contact.email.get' || service === 'statement.pdf.send') {
      record = customers.get(String(data.customerNo))?.services[service];
      if (service === 'statement.pdf.send' && !cards.get('cards.balance')?.has(data.cardNumber)) return notFound(service);
    } else {
      record = cards.get(service)?.get(data.cardNumber);
      if (service === 'statement.week.decide' || service === 'statement.week.change') {
        const week = String(data.newStatementWeek);
        record = record && Object.hasOwn(record, week) ? record[week] : undefined;
      }
    }
    if (!record) return notFound(service);
    if (record.delaySeconds) await new Promise(resolve => setTimeout(resolve, record.delaySeconds * 1000));
    return json(record.response, record.http);
  },
};
