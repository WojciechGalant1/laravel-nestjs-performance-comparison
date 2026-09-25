import { Controller, Get, Req, UseGuards } from '@nestjs/common';
import { Request } from 'express';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { BindDishGuard } from '../common/bind-entity.guard';
import type { Dish } from '../entities/dish.entity';
import { DishesService } from './dishes.service';

@Controller('dishes')
@UseGuards(JwtAuthGuard)
export class DishesController {
  constructor(private readonly dishesService: DishesService) {}

  // EP5: GET /api/dishes/:id/ingredients
  @Get(':id/ingredients')
  @UseGuards(BindDishGuard)
  ingredients(@Req() req: Request & { boundDish: Dish }) {
    return this.dishesService.ingredients(req.boundDish);
  }
}
