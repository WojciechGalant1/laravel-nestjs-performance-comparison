import { CanActivate, ExecutionContext, Injectable, NotFoundException } from '@nestjs/common';
import { Request } from 'express';
import { Dish } from '../entities/dish.entity';
import { Order } from '../entities/order.entity';

/**
 * Route-model-binding analogue. Guards run BEFORE interceptors in NestJS, so the
 * primary-key lookup happens outside QueryCountInterceptor — matching Laravel,
 * where SubstituteBindings resolves {order}/{dish} before count.queries starts.
 */
@Injectable()
export class BindOrderGuard implements CanActivate {
  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<Request & { boundOrder?: Order }>();
    const id = Number.parseInt(String(req.params.id), 10);

    if (Number.isNaN(id)) {
      throw new NotFoundException();
    }

    const order = await Order.findOne({ where: { id } });

    if (!order) {
      throw new NotFoundException();
    }

    req.boundOrder = order;
    return true;
  }
}

@Injectable()
export class BindDishGuard implements CanActivate {
  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest<Request & { boundDish?: Dish }>();
    const id = Number.parseInt(String(req.params.id), 10);

    if (Number.isNaN(id)) {
      throw new NotFoundException();
    }

    const dish = await Dish.findOne({ where: { id } });

    if (!dish) {
      throw new NotFoundException();
    }

    req.boundDish = dish;
    return true;
  }
}
