<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /**
     * PostgreSQL native enum types and the btree_gist extension required by
     * the reservations exclusion constraint. Created before any table so that
     * columns can reference these types directly.
     */
    public function up(): void
    {
        DB::statement('CREATE EXTENSION IF NOT EXISTS btree_gist');

        $this->createEnum('user_role', ['manager', 'waiter']);
        $this->createEnum('table_status', ['available', 'occupied', 'reserved', 'cleaning']);
        $this->createEnum('dish_category', ['starter', 'main', 'dessert', 'drink', 'side']);
        $this->createEnum('reservation_status', ['pending', 'confirmed', 'cancelled']);
        $this->createEnum('order_status', ['open', 'paid', 'cancelled']);
        $this->createEnum('order_item_status', ['pending', 'in_progress', 'completed', 'cancelled']);
    }

    public function down(): void
    {
        DB::statement('DROP TYPE IF EXISTS order_item_status');
        DB::statement('DROP TYPE IF EXISTS order_status');
        DB::statement('DROP TYPE IF EXISTS reservation_status');
        DB::statement('DROP TYPE IF EXISTS dish_category');
        DB::statement('DROP TYPE IF EXISTS table_status');
        DB::statement('DROP TYPE IF EXISTS user_role');

        DB::statement('DROP EXTENSION IF EXISTS btree_gist');
    }

    /**
     * Create a native PostgreSQL enum type idempotently. `migrate:fresh` drops
     * tables but not types, so re-running this migration must not fail if the
     * type already exists.
     *
     * @param  array<int, string>  $values
     */
    private function createEnum(string $name, array $values): void
    {
        $labels = collect($values)
            ->map(fn (string $value) => "'".$value."'")
            ->implode(', ');

        DB::statement("
            DO $$ BEGIN
                CREATE TYPE {$name} AS ENUM ({$labels});
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        ");
    }
};
