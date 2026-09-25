<?php

use Illuminate\Support\Facades\Route;

Route::get('/', fn () => response()->json(['api' => 'restaurant', 'status' => 'ok']));
