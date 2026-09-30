import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { OrderItem } from '../entities/order-item.entity';

const REFERENCE_FALLBACK = '2026-09-01 00:00:00';
const WINDOW_DAYS = 30;

@Injectable()
export class DashboardService {
  constructor(private readonly config: ConfigService) {}

  // EP6: sales statistics per dish category over the 30 days up to the frozen
  // benchmark reference date (BENCH_NOW), so the result set does not drift over time.
  // 3 JOIN (order_items -> orders, order_items -> menu_items -> dishes),
  // GROUP BY dishes.category, COUNT(DISTINCT)/SUM/AVG aggregations.
  // Written to mirror the Laravel DashboardService query (single SQL statement).
  async getSummary(): Promise<{ period: string; categories: unknown[] }> {
    const since = this.windowStart();

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

  // Passed to the query as a plain "Y-m-d H:i:s" string (ordered_at is a
  // timestamp without time zone), exactly as Laravel does, so both applications
  // send a byte-identical bound with no time-zone conversion in between.
  private windowStart(): string {
    const reference = new Date(
      `${(this.config.get<string>('BENCH_NOW') ?? REFERENCE_FALLBACK).replace(' ', 'T')}Z`,
    );
    reference.setUTCDate(reference.getUTCDate() - WINDOW_DAYS);

    return reference.toISOString().slice(0, 19).replace('T', ' ');
  }
}
