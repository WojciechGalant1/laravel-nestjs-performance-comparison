import { IsEnum } from 'class-validator';
import { OrderStatus } from '../../entities/enums';

export class UpdateOrderStatusDto {
  @IsEnum(OrderStatus)
  status: OrderStatus;
}
