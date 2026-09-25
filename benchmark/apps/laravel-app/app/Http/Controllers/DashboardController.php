<?php

namespace App\Http\Controllers;

use App\Services\DashboardService;
use Illuminate\Http\JsonResponse;

class DashboardController extends Controller
{
    public function __construct(
        private DashboardService $dashboard,
    ) {}

    /**
     * EP6: GET /api/dashboard/summary — 3 JOIN + GROUP BY + aggregations
     * Sales statistics per dish category (last 30 days).
     */
    public function summary(): JsonResponse
    {
        $data = $this->dashboard->getSummary();

        return response()->json($data);
    }
}
