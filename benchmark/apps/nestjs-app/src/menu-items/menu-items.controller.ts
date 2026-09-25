import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { resolvePage } from '../common/pagination';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { MenuItemsService } from './menu-items.service';

@Controller('menu-items')
@UseGuards(JwtAuthGuard)
export class MenuItemsController {
  constructor(private readonly menuItemsService: MenuItemsService) {}

  // EP2: GET /api/menu-items
  @Get()
  index(@Query('page') page?: string) {
    return this.menuItemsService.index(resolvePage(page));
  }
}
