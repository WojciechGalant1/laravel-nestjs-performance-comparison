<?php

namespace App\Http\Controllers;

use App\Models\Table;
use Illuminate\Http\JsonResponse;

class TableController extends Controller
{
    /**
     * EP1: GET /api/tables — Baseline (0 JOIN)
     * Simple paginated list of tables.
     */
    public function index(): JsonResponse
    {
        $tables = Table::query()
            ->orderBy('table_number')
            ->paginate(20);

        return response()->json($tables);
    }
}
