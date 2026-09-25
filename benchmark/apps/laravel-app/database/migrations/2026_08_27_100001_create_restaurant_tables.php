<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('tables', function (Blueprint $table) {
            $table->id();
            $table->integer('table_number')->unique();
            $table->integer('capacity');
            $table->timestamps();
        });
        DB::statement("ALTER TABLE tables ADD COLUMN status table_status NOT NULL DEFAULT 'available'");
        DB::statement('CREATE INDEX tables_status_index ON tables (status)');

        Schema::create('ingredients', function (Blueprint $table) {
            $table->id();
            $table->string('name');
            $table->string('unit');
            $table->timestamps();
        });

        Schema::create('dishes', function (Blueprint $table) {
            $table->id();
            $table->string('name');
            $table->timestamps();
        });
        DB::statement('ALTER TABLE dishes ADD COLUMN category dish_category NOT NULL');

        Schema::create('dish_ingredients', function (Blueprint $table) {
            $table->id();
            $table->foreignId('dish_id')->constrained()->cascadeOnDelete();
            $table->foreignId('ingredient_id')->constrained()->cascadeOnDelete();
            $table->decimal('quantity', 8, 2);
            $table->timestamps();

            $table->index('dish_id');
            $table->index('ingredient_id');
            $table->unique(['dish_id', 'ingredient_id']);
        });

        Schema::create('menu_items', function (Blueprint $table) {
            $table->id();
            $table->foreignId('dish_id')->constrained()->cascadeOnDelete();
            $table->decimal('price', 8, 2);
            $table->boolean('is_available')->default(true);
            $table->timestamps();

            $table->index('dish_id');
            $table->index('is_available');
        });

        Schema::create('reservations', function (Blueprint $table) {
            $table->id();
            $table->foreignId('table_id')->constrained()->cascadeOnDelete();
            $table->string('customer_name');
            $table->string('phone_number');
            $table->date('reservation_date');
            $table->time('reservation_time');
            $table->integer('party_size');
            $table->integer('duration_minutes')->default(120);
            $table->text('notes')->nullable();
            $table->timestamps();

            $table->index('table_id');
            $table->index('reservation_date');
        });
        DB::statement("ALTER TABLE reservations ADD COLUMN status reservation_status NOT NULL DEFAULT 'pending'");
        DB::statement('CREATE INDEX reservations_status_index ON reservations (status)');
        DB::statement("
            ALTER TABLE reservations
            ADD CONSTRAINT reservations_no_overlap
            EXCLUDE USING gist (
                table_id WITH =,
                tsrange(
                    (reservation_date + reservation_time),
                    (reservation_date + reservation_time + make_interval(mins => duration_minutes))
                ) WITH &&
            ) WHERE (status <> 'cancelled')
        ");

        Schema::create('orders', function (Blueprint $table) {
            $table->id();
            $table->foreignId('table_id')->constrained()->cascadeOnDelete();
            $table->foreignId('user_id')->nullable()->constrained()->cascadeOnDelete();
            $table->decimal('total_price', 10, 2)->default(0);
            $table->timestamp('ordered_at')->useCurrent();
            $table->timestamps();

            $table->index('table_id');
            $table->index('user_id');
            $table->index('ordered_at');
        });
        DB::statement("ALTER TABLE orders ADD COLUMN status order_status NOT NULL DEFAULT 'open'");
        DB::statement('CREATE INDEX orders_status_index ON orders (status)');

        Schema::create('order_items', function (Blueprint $table) {
            $table->id();
            $table->foreignId('order_id')->constrained()->cascadeOnDelete();
            $table->foreignId('menu_item_id')->constrained()->cascadeOnDelete();
            $table->integer('quantity');
            $table->decimal('unit_price', 8, 2);
            $table->text('notes')->nullable();
            $table->timestamps();

            $table->index('order_id');
            $table->index('menu_item_id');
        });
        DB::statement("ALTER TABLE order_items ADD COLUMN status order_item_status NOT NULL DEFAULT 'pending'");
        DB::statement('CREATE INDEX order_items_status_index ON order_items (status)');
    }

    public function down(): void
    {
        Schema::dropIfExists('order_items');
        Schema::dropIfExists('orders');
        Schema::dropIfExists('reservations');
        Schema::dropIfExists('menu_items');
        Schema::dropIfExists('dish_ingredients');
        Schema::dropIfExists('dishes');
        Schema::dropIfExists('ingredients');
        Schema::dropIfExists('tables');
    }
};
