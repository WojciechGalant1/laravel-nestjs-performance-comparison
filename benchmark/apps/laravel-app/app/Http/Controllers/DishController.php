<?php

namespace App\Http\Controllers;

use App\Models\Dish;
use Illuminate\Http\JsonResponse;

class DishController extends Controller
{
    /**
     * EP5: GET /api/dishes/{id}/ingredients — N:M through pivot (2 JOIN)
     * Dish with its ingredients via dish_ingredients pivot table.
     */
    public function ingredients(Dish $dish): JsonResponse
    {
        $dish->load('ingredients');

        return response()->json($dish);
    }
}
