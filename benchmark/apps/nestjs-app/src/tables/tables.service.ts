import { Injectable } from '@nestjs/common';
import { paginate, Paginated, PER_PAGE } from '../common/pagination';
import { RestaurantTable } from '../entities/restaurant-table.entity';

@Injectable()
export class TablesService {
  // EP1: baseline paginated list (no relations), ordered by table_number.
  async index(page: number): Promise<Paginated<RestaurantTable>> {
    const [data, total] = await RestaurantTable.findAndCount({
      order: { tableNumber: 'ASC' },
      skip: (page - 1) * PER_PAGE,
      take: PER_PAGE,
    });

    return paginate(data, total, page, '/api/tables');
  }
}
