<?php

namespace App\Auth;

use App\Enums\UserRole;
use App\Models\User;
use PHPOpenSourceSaver\JWTAuth\JWTGuard;

/**
 * Resolves the authenticated user from the signed JWT claims (sub, role)
 * without a database lookup, matching the NestJS JwtStrategy.
 *
 * Credential verification on login still loads the user (JWTGuard::attempt).
 */
class ClaimJwtGuard extends JWTGuard
{
    public function user()
    {
        if (null !== $this->user) {
            return $this->user;
        }

        if (
            ! $this->jwt->setRequest($this->request)->getToken()
            || ! ($payload = $this->jwt->check(true))
            || ! $this->validateSubject()
        ) {
            return null;
        }

        $role = UserRole::tryFrom((string) $payload->get('role'));
        $subject = $payload->get('sub');

        if ($role === null || $subject === null || $subject === '') {
            return null;
        }

        $user = new User;
        $user->forceFill([
            'id' => (int) $subject,
            'role' => $role->value,
        ]);
        $user->exists = true;

        $this->setUser($user);

        return $this->user;
    }
}
