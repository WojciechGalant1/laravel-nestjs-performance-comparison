import { AbstractLogger, LogLevel, LogMessage, QueryRunner } from 'typeorm';
import { queryCountStorage } from './query-context';

// Custom TypeORM logger that increments the per-request query counter held in
// AsyncLocalStorage. When no store is active (i.e. the request did not carry the
// X-Debug-Queries header), logging is a no-op, matching the Laravel middleware
// which only enables DB::getQueryLog() for diagnostic requests.
export class QueryCountLogger extends AbstractLogger {
  protected writeLog(_level: LogLevel, _logMessage: LogMessage | LogMessage[]): void {
    // Intentionally silent: this logger exists only to count queries below.
  }

  logQuery(query: string, _parameters?: unknown[], _queryRunner?: QueryRunner): void {
    const store = queryCountStorage.getStore();
    if (store) {
      store.count += 1;
      store.queries.push(query);
    }
  }
}
