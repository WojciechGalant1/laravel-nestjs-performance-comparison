import {
  Body,
  Controller,
  Get,
  HttpCode,
  Patch,
  Post,
  Query,
  Req,
  UseGuards,
} from '@nestjs/common';
import { Request } from 'express';
import { CurrentUser } from '../auth/auth-user';
import type { AuthUser } from '../auth/auth-user';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { BindOrderGuard } from '../common/bind-entity.guard';
import { resolvePage } from '../common/pagination';
import type { Order } from '../entities/order.entity';
import { CreateOrderDto } from './dto/create-order.dto';
import { UpdateOrderStatusDto } from './dto/update-order-status.dto';
import { OrdersService } from './orders.service';

@Controller('orders')
@UseGuards(JwtAuthGuard)
export class OrdersController {
  constructor(private readonly ordersService: OrdersService) {}

  // EP3: GET /api/orders
  @Get()
  index(@CurrentUser() user: AuthUser, @Query('page') page?: string) {
    return this.ordersService.index(user, resolvePage(page));
  }

  // EP4: GET /api/orders/:id
  @Get(':id')
  @UseGuards(BindOrderGuard)
  show(@CurrentUser() user: AuthUser, @Req() req: Request & { boundOrder: Order }) {
    return this.ordersService.show(user, req.boundOrder);
  }

  // EP7: POST /api/orders
  @Post()
  @HttpCode(201)
  create(@CurrentUser() user: AuthUser, @Body() dto: CreateOrderDto) {
    return this.ordersService.createOrder(dto, user);
  }

  // EP8: PATCH /api/orders/:id/status
  @Patch(':id/status')
  @UseGuards(BindOrderGuard)
  updateStatus(
    @CurrentUser() user: AuthUser,
    @Req() req: Request & { boundOrder: Order },
    @Body() dto: UpdateOrderStatusDto,
  ) {
    return this.ordersService.updateStatus(user, req.boundOrder, dto.status);
  }
}
