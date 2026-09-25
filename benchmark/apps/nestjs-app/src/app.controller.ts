import { Controller, Get } from '@nestjs/common';

@Controller()
export class AppController {
  // Health endpoint (parity with the Laravel web.php root route).
  @Get()
  health() {
    return { api: 'restaurant', status: 'ok' };
  }
}
