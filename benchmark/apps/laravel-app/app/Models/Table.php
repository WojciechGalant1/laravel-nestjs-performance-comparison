<?php

namespace App\Models;

use App\Enums\TableStatus;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class Table extends Model
{
    use HasFactory;

    protected $fillable = [
        'table_number',
        'capacity',
        'status',
    ];

    protected $casts = [
        'status' => TableStatus::class,
        'capacity' => 'integer',
        'table_number' => 'integer',
    ];

    // --- Relationships ---

    public function reservations()
    {
        return $this->hasMany(Reservation::class);
    }

    public function orders()
    {
        return $this->hasMany(Order::class);
    }

    // --- Domain methods ---

    public function markAsOccupied(): void
    {
        $this->update(['status' => TableStatus::Occupied]);
    }

    public function markAsAvailable(): void
    {
        $this->update(['status' => TableStatus::Available]);
    }

    public function markAsReserved(): void
    {
        $this->update(['status' => TableStatus::Reserved]);
    }

    public function markAsCleaning(): void
    {
        $this->update(['status' => TableStatus::Cleaning]);
    }
}
