<?php

namespace App\Exceptions;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use RuntimeException;

class BusinessRuleException extends RuntimeException
{
    public function __construct(
        string $message,
        private readonly int $status = 422,
    ) {
        parent::__construct($message);
    }

    public function render(Request $request): JsonResponse
    {
        return response()->json(['message' => $this->getMessage()], $this->status);
    }

    /**
     * Business-rule violations are expected under load (e.g. EP9 reservation
     * collisions) and must not be logged as errors.
     */
    public function report(): bool
    {
        return false;
    }
}
