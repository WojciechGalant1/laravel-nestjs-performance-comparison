import { Controller, Get, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from './auth/jwt-auth.guard';

/**
 * Diagnostic, not part of H1. Same JWT path as the measured endpoints,
 * fixed body, no database access: routing and per-request bootstrap only.
 */
@Controller('ping')
@UseGuards(JwtAuthGuard)
export class PingController {
  @Get()
  ping() {
    return { status: 'ok' };
  }
}
