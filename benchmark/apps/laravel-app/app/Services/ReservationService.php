<?php

namespace App\Services;

use App\Enums\ReservationStatus;
use App\Exceptions\BusinessRuleException;
use App\Models\Reservation;
use App\Models\Table;
use Illuminate\Database\QueryException;

class ReservationService
{
    /**
     * EP9: Create reservation, relying on a database-level exclusion
     * constraint (EXCLUDE USING gist) to detect overlapping time slots
     * atomically and without a read-then-write race condition.
     *
     * 1. Validate table exists and has sufficient capacity
     * 2. INSERT reservation; overlap is rejected by the DB constraint
     */
    public function createReservation(array $data): Reservation
    {
        $table = Table::findOrFail($data['table_id']);

        if ($table->capacity < $data['party_size']) {
            throw new BusinessRuleException('Party size exceeds table capacity.', 422);
        }

        try {
            return Reservation::create([
                'table_id' => $data['table_id'],
                'customer_name' => $data['customer_name'],
                'phone_number' => $data['phone_number'],
                'reservation_date' => $data['reservation_date'],
                'reservation_time' => $data['reservation_time'],
                'party_size' => $data['party_size'],
                'duration_minutes' => $data['duration_minutes'] ?? 120,
                'status' => ReservationStatus::Pending,
                'notes' => $data['notes'] ?? null,
            ]);
        } catch (QueryException $e) {
            // SQLSTATE 23P01 = exclusion_violation (overlapping reservation)
            if ($e->getCode() === '23P01') {
                throw new BusinessRuleException('Time slot conflicts with an existing reservation.', 409);
            }

            throw $e;
        }
    }
}
