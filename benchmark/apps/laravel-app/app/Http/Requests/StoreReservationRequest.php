<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreReservationRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'table_id' => 'required|integer|exists:tables,id',
            'customer_name' => 'required|string|max:255',
            'phone_number' => 'required|string|max:20',
            'reservation_date' => 'required|date|after_or_equal:today',
            'reservation_time' => 'required|date_format:H:i',
            'party_size' => 'required|integer|min:1|max:20',
            'duration_minutes' => 'nullable|integer|min:30|max:480',
            'notes' => 'nullable|string|max:1000',
        ];
    }
}
