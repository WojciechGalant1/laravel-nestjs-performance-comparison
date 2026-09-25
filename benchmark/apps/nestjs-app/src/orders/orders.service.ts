import { ForbiddenException, Injectable } from '@nestjs/common';
import { InjectDataSource } from '@nestjs/typeorm';
import { DataSource, In } from 'typeorm';
import { AuthUser } from '../auth/auth-user';
import { BusinessRuleException } from '../common/business-rule.exception';
import { paginate, Paginated, PER_PAGE } from '../common/pagination';
import { MenuItem } from '../entities/menu-item.entity';
import { Order } from '../entities/order.entity';
import { OrderItem } from '../entities/order-item.entity';
import { RestaurantTable } from '../entities/restaurant-table.entity';
import { User } from '../entities/user.entity';
import { OrderItemStatus, OrderStatus, UserRole } from '../entities/enums';
import { CreateOrderDto } from './dto/create-order.dto';

@Injectable()
export class OrdersService {
  constructor(@InjectDataSource() private readonly dataSource: DataSource) {}

  // EP3: paginated orders with table + waiter. Managers see all orders; waiters
  // see only their own (WHERE user_id = :id), mirroring Order::scopeForUser.
  async index(user: AuthUser, page: number): Promise<Paginated<Order>> {
    const where = user.role === UserRole.Manager ? {} : { userId: user.userId };

    const [data, total] = await Order.findAndCount({
      where,
      relations: { table: true, waiter: true },
      order: { orderedAt: 'DESC' },
      skip: (page - 1) * PER_PAGE,
      take: PER_PAGE,
    });

    return paginate(data, total, page, '/api/orders');
  }

  // EP4: 3-level nested eager load. The order row itself is already resolved by
  // BindOrderGuard (excluded from the S3 counter, like Laravel route-model
  // binding). Only relation hydration queries are issued here, sequentially,
  // matching Eloquent's $order->load(['table', 'waiter', 'orderItems.menuItem.dish']).
  async show(user: AuthUser, order: Order): Promise<Order> {
    this.authorizeOwnership(user, order);

    order.table = (await RestaurantTable.findOneBy({ id: order.tableId })) as RestaurantTable;
    order.waiter = order.userId
      ? ((await User.findOneBy({ id: order.userId })) as User)
      : (null as unknown as User);
    order.orderItems = await OrderItem.find({
      where: { orderId: order.id },
      relations: { menuItem: { dish: true } },
    });

    return order;
  }

  // EP7: create an order with its items in a single transaction.
  async createOrder(dto: CreateOrderDto, user: AuthUser): Promise<Order> {
    return this.dataSource.transaction(async (manager) => {
      const menuItemIds = [...new Set(dto.items.map((item) => item.menu_item_id))];

      const menuItems = await manager.find(MenuItem, {
        where: { id: In(menuItemIds), isAvailable: true },
      });

      if (menuItems.length !== menuItemIds.length) {
        throw new BusinessRuleException('One or more menu items are unavailable.', 422);
      }

      const priceById = new Map(menuItems.map((item) => [item.id, item.price]));

      const order = manager.create(Order, {
        tableId: dto.table_id,
        userId: user.userId,
        status: OrderStatus.Open,
        totalPrice: '0',
        orderedAt: new Date(),
      });
      await manager.save(order);

      // Accumulate the total in integer cents to avoid floating-point drift.
      let totalCents = 0;
      const items = dto.items.map((item) => {
        const unitPrice = priceById.get(item.menu_item_id) as string;
        totalCents += Math.round(parseFloat(unitPrice) * 100) * item.quantity;

        return manager.create(OrderItem, {
          orderId: order.id,
          menuItemId: item.menu_item_id,
          quantity: item.quantity,
          unitPrice,
          notes: item.notes ?? null,
          status: OrderItemStatus.Pending,
        });
      });
      await manager.save(items);

      order.totalPrice = (totalCents / 100).toFixed(2);
      await manager.save(order);

      order.orderItems = items;
      return order;
    });
  }

  // EP8: update an order's status (simple UPDATE). The order is already bound.
  async updateStatus(user: AuthUser, order: Order, status: OrderStatus): Promise<Order> {
    this.authorizeOwnership(user, order);

    order.status = status;
    await order.save();

    return order;
  }

  // OrderPolicy parity: a Manager may act on any order; a Waiter only on their own.
  private authorizeOwnership(user: AuthUser, order: Order): void {
    if (user.role !== UserRole.Manager && order.userId !== user.userId) {
      throw new ForbiddenException();
    }
  }
}
