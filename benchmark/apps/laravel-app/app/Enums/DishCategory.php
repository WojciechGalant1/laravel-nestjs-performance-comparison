<?php

namespace App\Enums;

enum DishCategory: string
{
    case Starter = 'starter';
    case Main = 'main';
    case Dessert = 'dessert';
    case Drink = 'drink';
    case Side = 'side';

    public function label(): string
    {
        return match($this) {
            self::Starter => 'Starter',
            self::Main => 'Main Course',
            self::Dessert => 'Dessert',
            self::Drink => 'Drink',
            self::Side => 'Side Dish',
        };
    }
}
