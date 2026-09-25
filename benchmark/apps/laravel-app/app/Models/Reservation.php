<?php

namespace App\Models;

use App\Enums\ReservationStatus;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class Reservation extends Model
{
    use HasFactory;

    protected $fillable = [
        'table_id',
        'customer_name',
        'phone_number',
        'reservation_date',
        'reservation_time',
        'party_size',
        'duration_minutes',
        'status',
        'notes',
    ];

    protected $casts = [
        'status' => ReservationStatus::class,
        'reservation_date' => 'date',
        'reservation_time' => 'datetime',
        'duration_minutes' => 'integer',
    ];

    public function table()
    {
        return $this->belongsTo(Table::class);
    }
}
