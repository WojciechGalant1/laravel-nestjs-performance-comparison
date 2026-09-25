<?php

namespace App\Models;

use App\Models\Dish;
use App\Models\OrderItem;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class MenuItem extends Model
{
    use HasFactory;

    protected $fillable = [
        'dish_id',
        'price',
        'is_available',
    ];

    public function dish()
    {
        return $this->belongsTo(Dish::class);
    }

    public function orderItems()
    {
        return $this->hasMany(OrderItem::class);
    }
}
