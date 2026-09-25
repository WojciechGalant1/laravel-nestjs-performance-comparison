<?php

namespace App\Enums;

enum OrderStatus: string
{
    case Open = 'open';
    case Paid = 'paid';
    case Cancelled = 'cancelled';

    public function label(): string
    {
        return match($this) {
            self::Open => 'Open',
            self::Paid => 'Paid',
            self::Cancelled => 'Cancelled',
        };
    }
}
