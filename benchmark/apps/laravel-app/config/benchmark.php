<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Benchmark reference timestamp
    |--------------------------------------------------------------------------
    |
    | Fixed point in time that anchors both the seeded dataset (order and
    | reservation dates) and the EP6 aggregation window. Without it the 30-day
    | window would be measured from the wall clock while the data stays frozen
    | in the database template, so the size of the EP6 result set would shrink
    | with every day that passes between seeding and the measurement, making
    | runs from different days incomparable.
    |
    | Both applications read the same value from the environment.
    |
    */

    'now' => env('BENCH_NOW', '2026-09-01 00:00:00'),

];
