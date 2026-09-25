<?php

namespace App\Models;

use App\Enums\OrderStatus;
use App\Enums\UserRole;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class Order extends Model
{
    use HasFactory;

    protected $fillable = [
        'table_id',
        'user_id',
        'status',
        'total_price',
        'ordered_at',
    ];

    protected $casts = [
        'status' => OrderStatus::class,
        'ordered_at' => 'datetime',
        'total_price' => 'decimal:2',
    ];

    // --- Scopes ---

    public function scopeForUser($query, User $user)
    {
        if ($user->role === UserRole::Manager) {
            return $query;
        }

        return $query->where('user_id', $user->id);
    }

    // --- Relationships ---

    public function table()
    {
        return $this->belongsTo(Table::class);
    }

    public function waiter()
    {
        return $this->belongsTo(User::class, 'user_id');
    }

    public function orderItems()
    {
        return $this->hasMany(OrderItem::class);
    }
}
