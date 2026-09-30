<?php

namespace App\Services;

use App\Models\OrderItem;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;

class DashboardService
{
    /**
     * EP6: Sales statistics per dish category (30 days up to the frozen
     * benchmark reference date, so the result set does not drift over time).
     *
     * 3 JOIN: order_items → orders, order_items → menu_items → dishes
     * GROUP BY: dishes.category
     * Aggregations: COUNT(DISTINCT), SUM, AVG
     */
    public function getSummary(): array
    {
        $since = Carbon::parse(config('benchmark.now'), 'UTC')
            ->subDays(30)
            ->toDateTimeString();

        $results = OrderItem::query()
            ->join('orders', 'order_items.order_id', '=', 'orders.id')
            ->join('menu_items', 'order_items.menu_item_id', '=', 'menu_items.id')
            ->join('dishes', 'menu_items.dish_id', '=', 'dishes.id')
            ->where('orders.ordered_at', '>=', $since)
            ->where('orders.status', '!=', 'cancelled')
            ->groupBy('dishes.category')
            ->select([
                'dishes.category',
                DB::raw('COUNT(DISTINCT orders.id) as orders_count'),
                DB::raw('SUM(order_items.quantity) as items_sold'),
                DB::raw('SUM(order_items.quantity * order_items.unit_price) as revenue'),
                DB::raw('AVG(order_items.quantity * order_items.unit_price) as avg_item_value'),
            ])
            ->orderByDesc('revenue')
            ->get();

        return [
            'period' => '30_days',
            'categories' => $results,
        ];
    }
}
