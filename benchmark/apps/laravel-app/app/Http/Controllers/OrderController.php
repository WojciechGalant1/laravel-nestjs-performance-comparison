<?php

namespace App\Http\Controllers;

use App\Models\Order;
use App\Http\Requests\StoreOrderRequest;
use App\Http\Requests\UpdateOrderStatusRequest;
use App\Services\OrderService;
use Illuminate\Http\JsonResponse;

class OrderController extends Controller
{
    public function __construct(
        private OrderService $orderService,
    ) {}

    /**
     * EP3: GET /api/orders — 2 JOIN (orders + tables + users)
     * Paginated list of orders with table and waiter info.
     * Waiter sees only own orders, Manager sees all.
     */
    public function index(): JsonResponse
    {
        $orders = Order::with(['table', 'waiter'])
            ->forUser(auth()->user())
            ->orderByDesc('ordered_at')
            ->paginate(20);

        return response()->json($orders);
    }

    /**
     * EP4: GET /api/orders/{id} — 4 JOIN (deep eager load)
     * Order details with items, menu items, dishes, and table.
     */
    public function show(Order $order): JsonResponse
    {
        $this->authorize('view', $order);

        $order->load([
            'table',
            'waiter',
            'orderItems.menuItem.dish',
        ]);

        return response()->json($order);
    }

    /**
     * EP7: POST /api/orders — Transactional write
     * Create order with items in a single transaction.
     */
    public function store(StoreOrderRequest $request): JsonResponse
    {
        $order = $this->orderService->createOrder(
            $request->validated(),
            auth()->user(),
        );

        return response()->json($order, 201);
    }

    /**
     * EP8: PATCH /api/orders/{id}/status — Simple UPDATE
     * Update order status with business validation.
     */
    public function updateStatus(UpdateOrderStatusRequest $request, Order $order): JsonResponse
    {
        $this->authorize('updateStatus', $order);

        $this->orderService->updateStatus($order, $request->validated()['status']);

        return response()->json($order);
    }
}
