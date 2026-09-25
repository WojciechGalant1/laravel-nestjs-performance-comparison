import { Injectable } from '@nestjs/common';
import { paginate, Paginated, PER_PAGE } from '../common/pagination';
import { MenuItem } from '../entities/menu-item.entity';

@Injectable()
export class MenuItemsService {
  // EP2: available menu items with their dish (1 relation, query-based eager load).
  async index(page: number): Promise<Paginated<MenuItem>> {
    const [data, total] = await MenuItem.findAndCount({
      where: { isAvailable: true },
      relations: { dish: true },
      skip: (page - 1) * PER_PAGE,
      take: PER_PAGE,
    });

    return paginate(data, total, page, '/api/menu-items');
  }
}
