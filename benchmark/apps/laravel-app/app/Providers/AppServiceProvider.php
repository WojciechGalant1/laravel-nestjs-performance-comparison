<?php

namespace App\Providers;

use App\Auth\ClaimJwtGuard;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\ServiceProvider;
use PHPOpenSourceSaver\JWTAuth\Factory;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        // Emit the same claim set as NestJS: {sub, role, iat, exp}. The package
        // default also adds iss, nbf and jti, which have no NestJS counterpart
        // and would make every request carry a larger Authorization header.
        $this->app->extend(
            'tymon.jwt.payload.factory',
            fn (Factory $factory) => $factory->setDefaultClaims(['iat', 'exp']),
        );
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        // Replaces the jwt-auth guard so protected requests trust the signed
        // claims instead of loading the user with SELECT ... WHERE id = sub.
        Auth::extend('jwt', function ($app, $name, array $config) {
            $guard = new ClaimJwtGuard(
                $app['tymon.jwt'],
                $app['auth']->createUserProvider($config['provider']),
                $app['request'],
                $app['events'],
            );

            $guard->setTTL($app->make('config')->get('jwt.ttl'));
            $app->refresh('request', $guard, 'setRequest');

            return $guard;
        });
    }
}
