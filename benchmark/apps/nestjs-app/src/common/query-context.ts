import { AsyncLocalStorage } from 'node:async_hooks';

export interface QueryCountStore {
  count: number;
  queries: string[];
}

// Per-request store for the S3 SQL-query counter. Established by
// QueryCountInterceptor only when the X-Debug-Queries header is present, so it
// carries zero overhead on benchmark traffic. AsyncLocalStorage guarantees that
// concurrent requests (interleaved on the Node.js event loop) each accumulate
// their own count without cross-talk.
export const queryCountStorage = new AsyncLocalStorage<QueryCountStore>();
