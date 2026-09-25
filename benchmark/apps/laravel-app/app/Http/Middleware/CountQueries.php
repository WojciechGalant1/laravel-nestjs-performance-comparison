<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Symfony\Component\HttpFoundation\Response;

/**
 * Diagnostic middleware for scenario S3 (SQL query counting).
 *
 * Activates only when the request carries the "X-Debug-Queries" header, so it
 * has zero overhead on load-test traffic (JMeter benchmark requests omit it).
 *
 * It is applied AFTER auth:api. Authentication resolves the user from the
 * signed claims and issues no SQL. Route-model binding is resolved earlier
 * in the api middleware group, so the reported count reflects purely the
 * controller/ORM hydration queries.
 */
class CountQueries
{
    public function handle(Request $request, Closure $next): Response
    {
        if (! $request->hasHeader('X-Debug-Queries')) {
            return $next($request);
        }

        DB::flushQueryLog();
        DB::enableQueryLog();

        $response = $next($request);

        $queries = DB::getQueryLog();
        $count = count($queries);

        Log::info('S3 query count', [
            'method' => $request->method(),
            'path' => $request->path(),
            'count' => $count,
            'queries' => array_map(static fn (array $q): string => $q['query'], $queries),
        ]);

        $response->headers->set('X-Query-Count', (string) $count);

        return $response;
    }
}
