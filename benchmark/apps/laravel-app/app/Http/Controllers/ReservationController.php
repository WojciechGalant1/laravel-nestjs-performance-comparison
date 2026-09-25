<?php

namespace App\Http\Controllers;

use App\Http\Requests\StoreReservationRequest;
use App\Services\ReservationService;
use Illuminate\Http\JsonResponse;

class ReservationController extends Controller
{
    public function __construct(
        private ReservationService $reservationService,
    ) {}

    /**
     * EP9: POST /api/reservations — Write with collision check
     * Create a reservation with time overlap validation.
     */
    public function store(StoreReservationRequest $request): JsonResponse
    {
        $reservation = $this->reservationService->createReservation(
            $request->validated(),
        );

        return response()->json($reservation, 201);
    }
}
