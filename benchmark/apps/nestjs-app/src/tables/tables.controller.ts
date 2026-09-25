import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { resolvePage } from '../common/pagination';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { TablesService } from './tables.service';

@Controller('tables')
@UseGuards(JwtAuthGuard)
export class TablesController {
  constructor(private readonly tablesService: TablesService) {}

  // EP1: GET /api/tables
  @Get()
  index(@Query('page') page?: string) {
    return this.tablesService.index(resolvePage(page));
  }
}
