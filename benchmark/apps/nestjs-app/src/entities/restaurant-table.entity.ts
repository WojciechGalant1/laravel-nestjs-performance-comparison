import {
  BaseEntity,
  Column,
  CreateDateColumn,
  Entity,
  OneToMany,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';
import { TableStatus } from './enums';
import { Order } from './order.entity';
import { Reservation } from './reservation.entity';

@Entity('tables')
export class RestaurantTable extends BaseEntity {
  @PrimaryGeneratedColumn({ type: 'bigint' })
  id: number;

  @Column({ name: 'table_number', type: 'int' })
  tableNumber: number;

  @Column({ type: 'int' })
  capacity: number;

  @Column({ type: 'enum', enum: TableStatus, enumName: 'table_status' })
  status: TableStatus;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp' })
  updatedAt: Date;

  @OneToMany(() => Order, (order) => order.table)
  orders: Order[];

  @OneToMany(() => Reservation, (reservation) => reservation.table)
  reservations: Reservation[];
}
