<?php

namespace Database\Seeders;

use Illuminate\Database\Seeder;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;

class RestaurantSeeder extends Seeder
{
    private const SEED = 20260101;

    private const USERS = 200;
    private const TABLES = 200;
    private const INGREDIENTS = 200;
    private const DISHES = 500;
    private const MENU_ITEMS = 500;
    private const INGREDIENTS_PER_DISH = 4;
    private const ORDERS = 100_000;
    private const RESERVATIONS_PER_TABLE = 500;

    private const CHUNK = 1000;

    private string $now;

    /** Unix timestamp of the frozen reference date the whole dataset is anchored to. */
    private int $referenceTs;

    /** @var string[] */
    private array $namePool = [];

    public function run(): void
    {
        mt_srand(self::SEED);
        fake()->seed(self::SEED);

        DB::connection()->disableQueryLog();

        // Anchor every generated date to the benchmark reference date instead of
        // the wall clock, so the dataset is identical no matter when it is seeded
        // and the EP6 window always covers the same rows.
        $reference = Carbon::parse(config('benchmark.now'), 'UTC');
        $this->referenceTs = $reference->getTimestamp();
        $this->now = $reference->toDateTimeString();

        // Reset to a known empty state with sequences restarting at 1, so that
        // generated foreign keys can rely on deterministic serial ids.
        DB::statement('TRUNCATE users, tables, ingredients, dishes, dish_ingredients, menu_items, orders, order_items, reservations RESTART IDENTITY CASCADE');

        $this->buildNamePool();

        $this->command->info('Seeding users, dictionary tables...');
        $this->seedUsers();
        $this->seedTables();
        $this->seedIngredients();
        $this->seedDishes();
        $this->seedDishIngredients();
        $prices = $this->seedMenuItems();

        $this->command->info('Seeding 100k orders + order items...');
        $this->seedOrders($prices);

        $this->command->info('Seeding 100k reservations...');
        $this->seedReservations();

        $this->command->info('Done.');
    }

    private function buildNamePool(): void
    {
        for ($i = 0; $i < 2000; $i++) {
            $this->namePool[] = fake()->firstName().' '.fake()->lastName();
        }
    }

    private function seedUsers(): void
    {
        $password = Hash::make('password');
        $rows = [];

        for ($i = 1; $i <= self::USERS; $i++) {
            [$first, $last] = explode(' ', $this->namePool[$i % count($this->namePool)], 2);

            $email = match ($i) {
                1 => 'manager@example.com',
                2 => 'waiter@example.com',
                default => 'user'.$i.'@example.com',
            };

            $rows[] = [
                'first_name' => $first,
                'last_name' => $last,
                'email' => $email,
                'password' => $password,
                'role' => $i <= 10 ? 'manager' : 'waiter',
                'created_at' => $this->now,
                'updated_at' => $this->now,
            ];
        }

        $this->insertChunked('users', $rows);
    }

    private function seedTables(): void
    {
        $rows = [];

        for ($i = 1; $i <= self::TABLES; $i++) {
            $rows[] = [
                'table_number' => $i,
                'capacity' => mt_rand(2, 12),
                'status' => mt_rand(1, 100) <= 70 ? 'available' : ['occupied', 'reserved', 'cleaning'][mt_rand(0, 2)],
                'created_at' => $this->now,
                'updated_at' => $this->now,
            ];
        }

        $this->insertChunked('tables', $rows);
    }

    private function seedIngredients(): void
    {
        $units = ['g', 'ml', 'szt'];
        $rows = [];

        for ($i = 1; $i <= self::INGREDIENTS; $i++) {
            $rows[] = [
                'name' => ucfirst(fake()->word()),
                'unit' => $units[mt_rand(0, 2)],
                'created_at' => $this->now,
                'updated_at' => $this->now,
            ];
        }

        $this->insertChunked('ingredients', $rows);
    }

    private function seedDishes(): void
    {
        $categories = ['starter', 'main', 'dessert', 'drink', 'side'];
        $rows = [];

        for ($i = 1; $i <= self::DISHES; $i++) {
            $rows[] = [
                'name' => ucfirst(fake()->words(2, true)),
                'category' => $categories[mt_rand(0, 4)],
                'created_at' => $this->now,
                'updated_at' => $this->now,
            ];
        }

        $this->insertChunked('dishes', $rows);
    }

    private function seedDishIngredients(): void
    {
        $rows = [];

        for ($dishId = 1; $dishId <= self::DISHES; $dishId++) {
            $picked = [];
            while (count($picked) < self::INGREDIENTS_PER_DISH) {
                $picked[mt_rand(1, self::INGREDIENTS)] = true;
            }

            foreach (array_keys($picked) as $ingredientId) {
                $rows[] = [
                    'dish_id' => $dishId,
                    'ingredient_id' => $ingredientId,
                    'quantity' => round(mt_rand(1, 5000) / 10, 2),
                    'created_at' => $this->now,
                    'updated_at' => $this->now,
                ];
            }

            if (count($rows) >= self::CHUNK) {
                $this->insertChunked('dish_ingredients', $rows);
                $rows = [];
            }
        }

        $this->insertChunked('dish_ingredients', $rows);
    }

    /**
     * @return array<int, float> menu_item id => price
     */
    private function seedMenuItems(): array
    {
        $prices = [];
        $rows = [];

        for ($dishId = 1; $dishId <= self::MENU_ITEMS; $dishId++) {
            $price = round(mt_rand(500, 10000) / 100, 2);
            $prices[$dishId] = $price; // menu_item serial id == $dishId on a fresh table

            $rows[] = [
                'dish_id' => $dishId,
                'price' => $price,
                'is_available' => mt_rand(1, 100) <= 90,
                'created_at' => $this->now,
                'updated_at' => $this->now,
            ];
        }

        $this->insertChunked('menu_items', $rows);

        return $prices;
    }

    /**
     * @param  array<int, float>  $prices
     */
    private function seedOrders(array $prices): void
    {
        $itemStatuses = ['pending', 'in_progress', 'completed', 'cancelled'];
        $nowTs = $this->referenceTs;
        $ninetyDays = 90 * 86400;

        $orders = [];
        $items = [];

        for ($orderId = 1; $orderId <= self::ORDERS; $orderId++) {
            $itemCount = mt_rand(1, 5);
            $total = 0.0;

            for ($j = 0; $j < $itemCount; $j++) {
                $menuItemId = mt_rand(1, self::MENU_ITEMS);
                $quantity = mt_rand(1, 5);
                $unitPrice = $prices[$menuItemId];
                $total += $quantity * $unitPrice;

                $items[] = [
                    'order_id' => $orderId,
                    'menu_item_id' => $menuItemId,
                    'quantity' => $quantity,
                    'unit_price' => $unitPrice,
                    'notes' => null,
                    'status' => $itemStatuses[mt_rand(0, 3)],
                    'created_at' => $this->now,
                    'updated_at' => $this->now,
                ];
            }

            $roll = mt_rand(1, 100);
            $status = $roll <= 70 ? 'paid' : ($roll <= 90 ? 'open' : 'cancelled');

            $orders[] = [
                'table_id' => mt_rand(1, self::TABLES),
                'user_id' => mt_rand(1, self::USERS),
                'status' => $status,
                'total_price' => round($total, 2),
                'ordered_at' => date('Y-m-d H:i:s', $nowTs - mt_rand(0, $ninetyDays)),
                'created_at' => $this->now,
                'updated_at' => $this->now,
            ];

            if ($orderId % self::CHUNK === 0) {
                $this->flushOrders($orders, $items);
            }
        }

        $this->flushOrders($orders, $items);
    }

    /**
     * Orders must be inserted before their items (FK), and in sequence so that
     * each order's serial id matches the loop counter used as order_id.
     *
     * @param  array<int, array<string, mixed>>  $orders
     * @param  array<int, array<string, mixed>>  $items
     */
    private function flushOrders(array &$orders, array &$items): void
    {
        if ($orders !== []) {
            DB::table('orders')->insert($orders);
            $orders = [];
        }

        if ($items !== []) {
            $this->insertChunked('order_items', $items);
            $items = [];
        }
    }

    private function seedReservations(): void
    {
        $slotTimes = ['12:00:00', '14:00:00', '16:00:00', '18:00:00', '20:00:00'];
        $slotsPerDay = count($slotTimes);
        $baseDate = $this->referenceTs - 50 * 86400;
        $statuses = ['pending', 'confirmed', 'cancelled'];

        $rows = [];

        for ($tableId = 1; $tableId <= self::TABLES; $tableId++) {
            for ($k = 0; $k < self::RESERVATIONS_PER_TABLE; $k++) {
                $day = intdiv($k, $slotsPerDay);
                $slot = $k % $slotsPerDay;

                $roll = mt_rand(1, 100);
                $status = $roll <= 60 ? 'confirmed' : ($roll <= 90 ? 'pending' : 'cancelled');

                $rows[] = [
                    'table_id' => $tableId,
                    'customer_name' => $this->namePool[mt_rand(0, count($this->namePool) - 1)],
                    'phone_number' => '+48'.mt_rand(500000000, 899999999),
                    'reservation_date' => date('Y-m-d', $baseDate + $day * 86400),
                    'reservation_time' => $slotTimes[$slot],
                    'party_size' => mt_rand(1, 8),
                    'duration_minutes' => 120,
                    'status' => $status,
                    'notes' => null,
                    'created_at' => $this->now,
                    'updated_at' => $this->now,
                ];

                if (count($rows) >= self::CHUNK) {
                    $this->insertChunked('reservations', $rows);
                    $rows = [];
                }
            }
        }

        $this->insertChunked('reservations', $rows);
    }

    /**
     * @param  array<int, array<string, mixed>>  $rows
     */
    private function insertChunked(string $table, array $rows): void
    {
        foreach (array_chunk($rows, self::CHUNK) as $chunk) {
            DB::table($table)->insert($chunk);
        }
    }
}
