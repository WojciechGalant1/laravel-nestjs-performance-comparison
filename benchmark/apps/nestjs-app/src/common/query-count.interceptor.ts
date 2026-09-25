import {
  CallHandler,
  ExecutionContext,
  Injectable,
  Logger,
  NestInterceptor,
} from '@nestjs/common';
import { Request, Response } from 'express';
import { from, lastValueFrom, Observable } from 'rxjs';
import { QueryCountStore, queryCountStorage } from './query-context';

// S3 diagnostic (parity with the Laravel CountQueries middleware). The very first
// check is the X-Debug-Queries header; when absent we return the handler stream
// untouched, guaranteeing zero overhead on benchmark traffic. When present, the
// whole handler runs inside an AsyncLocalStorage context so the QueryCountLogger
// can tally the SQL statements; the total is returned in the X-Query-Count header
// and the exact SQL is logged for inspection.
@Injectable()
export class QueryCountInterceptor implements NestInterceptor {
  private readonly logger = new Logger('S3QueryCount');

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const req = context.switchToHttp().getRequest<Request>();

    if (req.headers['x-debug-queries'] === undefined) {
      return next.handle();
    }

    const res = context.switchToHttp().getResponse<Response>();
    const store: QueryCountStore = { count: 0, queries: [] };

    return from(
      queryCountStorage.run(store, async () => {
        const result = await lastValueFrom(next.handle());
        res.setHeader('X-Query-Count', String(store.count));
        this.logger.log(
          `${req.method} ${req.originalUrl} count=${store.count} queries=${JSON.stringify(store.queries)}`,
        );
        return result;
      }),
    );
  }
}
