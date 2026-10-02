<?php

use App\Http\Controllers\AuthController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\DishController;
use App\Http\Controllers\MenuItemController;
use App\Http\Controllers\OrderController;
use App\Http\Controllers\PingController;
use App\Http\Controllers\ReservationController;
use App\Http\Controllers\TableController;
use Illuminate\Support\Facades\Route;

// EP10: authentication
Route::post('auth/login', [AuthController::class, 'login']);

Route::middleware(['auth:api', 'count.queries'])->group(function () {
    // Diagnostic: routing and framework bootstrap, no database access.
    Route::get('ping', PingController::class);

    // EP1: baseline (0 relations)
    Route::get('tables', [TableController::class, 'index']);

    // EP2: 1 relation
    Route::get('menu-items', [MenuItemController::class, 'index']);

    // EP3: 2 relations (eager)
    Route::get('orders', [OrderController::class, 'index']);

    // EP4: 3-level nested eager load
    Route::get('orders/{order}', [OrderController::class, 'show']);

    // EP5: N:M via pivot
    Route::get('dishes/{dish}/ingredients', [DishController::class, 'ingredients']);

    // EP6: 3 JOIN + aggregation
    Route::get('dashboard/summary', [DashboardController::class, 'summary']);

    // EP7: transactional insert
    Route::post('orders', [OrderController::class, 'store']);

    // EP8: simple UPDATE
    Route::patch('orders/{order}/status', [OrderController::class, 'updateStatus']);

    // EP9: insert + DB exclusion constraint
    Route::post('reservations', [ReservationController::class, 'store']);
});
