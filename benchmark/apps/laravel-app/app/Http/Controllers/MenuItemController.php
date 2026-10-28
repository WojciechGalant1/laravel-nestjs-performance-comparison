<?php

namespace App\Http\Controllers;

use App\Models\MenuItem;
use Illuminate\Http\JsonResponse;

class MenuItemController extends Controller
{
    /**
     * EP2: GET /api/menu-items — 1 JOIN
     * Available menu items with dish info.
     */
    public function index(): JsonResponse
    {
        $menuItems = MenuItem::with('dish')
            ->where('is_available', true)
            ->paginate(20);

        return response()->json($menuItems);
    }

    /**
     * EP2b: GET /api/menu-items/plain — same-table control for H3.
     * Same filter and pagination as EP2, but without loading `dish` (0 relations).
     */
    public function indexPlain(): JsonResponse
    {
        $menuItems = MenuItem::query()
            ->where('is_available', true)
            ->paginate(20);

        return response()->json($menuItems);
    }
}
