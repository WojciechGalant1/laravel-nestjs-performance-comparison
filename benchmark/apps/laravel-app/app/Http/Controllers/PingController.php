<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;

class PingController extends Controller
{
    /**
     * Diagnostic, not part of H1. Same JWT path as the measured endpoints,
     * fixed body, no database access: routing and per-request bootstrap only.
     */
    public function __invoke(): JsonResponse
    {
        return response()->json(['status' => 'ok']);
    }
}
