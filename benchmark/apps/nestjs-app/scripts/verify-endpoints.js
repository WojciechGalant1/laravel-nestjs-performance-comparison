const futureDate = new Date();
futureDate.setDate(futureDate.getDate() + 14);
const reservationDate = futureDate.toISOString().slice(0, 10);

async function request(base, path, { method = 'GET', token, body, debug } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (debug) headers['X-Debug-Queries'] = '1';

  const res = await fetch(`${base}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  return {
    status: res.status,
    bytes: Buffer.byteLength(text),
    queryCount: res.headers.get('x-query-count'),
    json: (() => {
      try {
        return JSON.parse(text);
      } catch {
        return text;
      }
    })(),
  };
}

async function login(base) {
  const res = await request(base, '/api/auth/login', {
    method: 'POST',
    body: { email: 'manager@example.com', password: 'password' },
  });
  if (!res.json.access_token) {
    throw new Error(`login failed on ${base}: ${res.status} ${JSON.stringify(res.json)}`);
  }
  return res.json.access_token;
}

(async () => {
  const nest = process.env.NEST_BASE || 'http://127.0.0.1:3000';
  const laravel = 'http://127.0.0.1:8000';

  const health = await request(nest, '/');
  console.log('health', health.status, JSON.stringify(health.json));

  const nestToken = await login(nest);
  console.log('login nest', 'ok', 'token_len=' + nestToken.length);

  let laravelToken = null;
  try {
    laravelToken = await login(laravel);
    console.log('login laravel', 'ok');
  } catch (error) {
    console.log('login laravel skipped:', error.message);
  }

  const readPaths = [
    '/api/tables',
    '/api/menu-items',
    '/api/orders',
    '/api/orders/5',
    '/api/dishes/5/ingredients',
    '/api/dashboard/summary',
  ];

  for (const path of readPaths) {
    const nestRes = await request(nest, path, { token: nestToken, debug: true });
    const line = {
      path,
      nest_status: nestRes.status,
      nest_bytes: nestRes.bytes,
      nest_queries: nestRes.queryCount,
    };

    if (laravelToken) {
      const laravelRes = await request(laravel, path, { token: laravelToken, debug: true });
      line.laravel_status = laravelRes.status;
      line.laravel_bytes = laravelRes.bytes;
      line.laravel_queries = laravelRes.queryCount;
      line.byte_diff_pct = (
        (Math.abs(nestRes.bytes - laravelRes.bytes) / Math.max(laravelRes.bytes, 1)) *
        100
      ).toFixed(1);
    }

    console.log(JSON.stringify(line));
    if (nestRes.status >= 400) {
      console.log('  nest body', JSON.stringify(nestRes.json).slice(0, 300));
    }
  }

  const created = await request(nest, '/api/orders', {
    method: 'POST',
    token: nestToken,
    body: { table_id: 1, items: [{ menu_item_id: 1, quantity: 2 }] },
  });
  console.log('EP7', created.status, 'id=' + created.json.id, 'total=' + created.json.total_price);

  const patched = await request(nest, `/api/orders/${created.json.id}/status`, {
    method: 'PATCH',
    token: nestToken,
    body: { status: 'paid' },
  });
  console.log('EP8', patched.status, 'status=' + patched.json.status);

  const reservation = await request(nest, '/api/reservations', {
    method: 'POST',
    token: nestToken,
    body: {
      table_id: 1,
      customer_name: 'Parity Test',
      phone_number: '+48123123123',
      reservation_date: reservationDate,
      reservation_time: '11:00',
      party_size: 2,
      duration_minutes: 60,
    },
  });
  console.log('EP9', reservation.status, reservation.status >= 400 ? JSON.stringify(reservation.json) : 'id=' + reservation.json.id);

  const conflict = await request(nest, '/api/reservations', {
    method: 'POST',
    token: nestToken,
    body: {
      table_id: 1,
      customer_name: 'Parity Test',
      phone_number: '+48123123123',
      reservation_date: reservationDate,
      reservation_time: '11:00',
      party_size: 2,
      duration_minutes: 60,
    },
  });
  console.log('EP9-conflict', conflict.status, JSON.stringify(conflict.json));

  const noDebug = await request(nest, '/api/orders/5', { token: nestToken });
  console.log('no-debug-header', noDebug.status, 'queryCount=' + noDebug.queryCount);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
