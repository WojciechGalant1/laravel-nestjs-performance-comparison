import {
  BaseEntity,
  Column,
  CreateDateColumn,
  Entity,
  JoinColumn,
  ManyToOne,
  OneToMany,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';
import { Dish } from './dish.entity';
import { OrderItem } from './order-item.entity';

@Entity('menu_items')
export class MenuItem extends BaseEntity {
  @PrimaryGeneratedColumn({ type: 'bigint' })
  id: number;

  @Column({ name: 'dish_id', type: 'bigint' })
  dishId: number;

  @Column({ type: 'decimal', precision: 8, scale: 2 })
  price: string;

  @Column({ name: 'is_available', type: 'boolean' })
  isAvailable: boolean;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp' })
  updatedAt: Date;

  @ManyToOne(() => Dish, (dish) => dish.menuItems)
  @JoinColumn({ name: 'dish_id' })
  dish: Dish;

  @OneToMany(() => OrderItem, (orderItem) => orderItem.menuItem)
  orderItems: OrderItem[];
}
