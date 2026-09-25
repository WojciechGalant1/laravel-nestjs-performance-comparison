import { Injectable } from '@nestjs/common';
import { OrderItem } from '../entities/order-item.entity';

@Injectable()
export class DashboardService {
  // EP6: sales statistics per dish category over the last 30 days.
  // 3 JOIN (order_items -> orders, order_items -> menu_items -> dishes),
  // GROUP BY dishes.category, COUNT(DISTINCT)/SUM/AVG aggregations.
  // Written to mirror the Laravel DashboardService query (single SQL statement).
  async getSummary(): Promise<{ period: string; categories: unknown[] }> {
    const since = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);

    const categories = await OrderItem.createQueryBuilder('order_items')
      .innerJoin('orders', 'orders', 'order_items.order_id = orders.id')
      .innerJoin('menu_items', 'menu_items', 'order_items.menu_item_id = menu_items.id')
      .innerJoin('dishes', 'dishes', 'menu_items.dish_id = dishes.id')
      .where('orders.ordered_at >= :since', { since })
      .andWhere('orders.status != :cancelled', { cancelled: 'cancelled' })
      .groupBy('dishes.category')
      .select('dishes.category', 'category')
      .addSelect('COUNT(DISTINCT orders.id)', 'orders_count')
      .addSelect('SUM(order_items.quantity)', 'items_sold')
      .addSelect('SUM(order_items.quantity * order_items.unit_price)', 'revenue')
      .addSelect('AVG(order_items.quantity * order_items.unit_price)', 'avg_item_value')
      .orderBy('revenue', 'DESC')
      .getRawMany();

    return {
      period: '30_days',
      categories,
    };
  }
}
