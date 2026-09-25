<?php

namespace App\Policies;

use App\Enums\UserRole;
use App\Models\Order;
use App\Models\User;

class OrderPolicy
{
    /**
     * Allow listing orders — filtering is done via query scope, not policy.
     */
    public function viewAny(User $user): bool
    {
        return true;
    }

    /**
     * Manager can view any order. Waiter can view only own orders.
     */
    public function view(User $user, Order $order): bool
    {
        return $user->role === UserRole::Manager
            || $order->user_id === $user->id;
    }

    /**
     * Manager can update status of any order. Waiter only own orders.
     */
    public function updateStatus(User $user, Order $order): bool
    {
        return $user->role === UserRole::Manager
            || $order->user_id === $user->id;
    }
}
