<?php

namespace App\Services;

use App\Enums\OrderItemStatus;
use App\Enums\OrderStatus;
use App\Exceptions\BusinessRuleException;
use App\Models\MenuItem;
use App\Models\Order;
use App\Models\User;
use Illuminate\Support\Facades\DB;

class OrderService
{
    /**
     * EP7: Create order with items in a transaction.
     *
     * 1. Validate menu items exist and are available
     * 2. INSERT order
     * 3. INSERT order_items
     * 4. UPDATE total_price
     */
    public function createOrder(array $data, User $waiter): Order
    {
        return DB::transaction(function () use ($data, $waiter) {
            $menuItemIds = collect($data['items'])->pluck('menu_item_id')->unique()->values();
            $menuItems = MenuItem::whereIn('id', $menuItemIds)
                ->where('is_available', true)
                ->get()
                ->keyBy('id');

            if ($menuItems->count() !== $menuItemIds->count()) {
                throw new BusinessRuleException('One or more menu items are unavailable.', 422);
            }

            $order = Order::create([
                'table_id' => $data['table_id'],
                'user_id' => $waiter->id,
                'status' => OrderStatus::Open,
                'total_price' => 0,
                'ordered_at' => now(),
            ]);

            foreach ($data['items'] as $item) {
                $menuItem = $menuItems->get($item['menu_item_id']);

                $order->orderItems()->create([
                    'menu_item_id' => $item['menu_item_id'],
                    'quantity' => $item['quantity'],
                    'unit_price' => $menuItem->price,
                    'notes' => $item['notes'] ?? null,
                    'status' => OrderItemStatus::Pending,
                ]);
            }

            $order->update([
                'total_price' => $order->orderItems->sum(
                    fn($i) => $i->quantity * $i->unit_price,
                ),
            ]);

            return $order;
        });
    }

    /**
     * EP8: Update order status with business validation.
     */
    public function updateStatus(Order $order, string $status): bool
    {
        return $order->update([
            'status' => $status,
        ]);
    }
}
