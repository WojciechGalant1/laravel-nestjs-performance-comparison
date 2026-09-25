import {
  BaseEntity,
  Column,
  CreateDateColumn,
  Entity,
  JoinColumn,
  ManyToOne,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';
import { ReservationStatus } from './enums';
import { RestaurantTable } from './restaurant-table.entity';

@Entity('reservations')
export class Reservation extends BaseEntity {
  @PrimaryGeneratedColumn({ type: 'bigint' })
  id: number;

  @Column({ name: 'table_id', type: 'bigint' })
  tableId: number;

  @Column({ name: 'customer_name', type: 'varchar' })
  customerName: string;

  @Column({ name: 'phone_number', type: 'varchar' })
  phoneNumber: string;

  @Column({ name: 'reservation_date', type: 'date' })
  reservationDate: string;

  @Column({ name: 'reservation_time', type: 'time' })
  reservationTime: string;

  @Column({ name: 'party_size', type: 'int' })
  partySize: number;

  @Column({ name: 'duration_minutes', type: 'int', default: 120 })
  durationMinutes: number;

  @Column({ type: 'text', nullable: true })
  notes: string | null;

  @Column({ type: 'enum', enum: ReservationStatus, enumName: 'reservation_status' })
  status: ReservationStatus;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp' })
  updatedAt: Date;

  @ManyToOne(() => RestaurantTable, (table) => table.reservations)
  @JoinColumn({ name: 'table_id' })
  table: RestaurantTable;
}
