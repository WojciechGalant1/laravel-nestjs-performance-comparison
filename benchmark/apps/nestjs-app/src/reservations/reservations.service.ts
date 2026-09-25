import { Injectable, NotFoundException } from '@nestjs/common';
import { BusinessRuleException } from '../common/business-rule.exception';
import { ReservationStatus } from '../entities/enums';
import { Reservation } from '../entities/reservation.entity';
import { RestaurantTable } from '../entities/restaurant-table.entity';
import { CreateReservationDto } from './dto/create-reservation.dto';

@Injectable()
export class ReservationsService {
  // EP9: create a reservation. Time-slot uniqueness is enforced by the database
  // EXCLUDE USING gist constraint; an overlap raises SQLSTATE 23P01, which we
  // translate into a 409 domain error (parity with ReservationService.php).
  async createReservation(dto: CreateReservationDto): Promise<Reservation> {
    const table = await RestaurantTable.findOne({ where: { id: dto.table_id } });

    if (!table) {
      throw new NotFoundException();
    }

    if (table.capacity < dto.party_size) {
      throw new BusinessRuleException('Party size exceeds table capacity.', 422);
    }

    const reservation = Reservation.create({
      tableId: dto.table_id,
      customerName: dto.customer_name,
      phoneNumber: dto.phone_number,
      reservationDate: dto.reservation_date,
      reservationTime: dto.reservation_time,
      partySize: dto.party_size,
      durationMinutes: dto.duration_minutes ?? 120,
      status: ReservationStatus.Pending,
      notes: dto.notes ?? null,
    });

    try {
      await reservation.save();
      return reservation;
    } catch (error) {
      const code =
        (error as { code?: string; driverError?: { code?: string } }).code ??
        (error as { driverError?: { code?: string } }).driverError?.code;

      if (code === '23P01') {
        throw new BusinessRuleException(
          'Time slot conflicts with an existing reservation.',
          409,
        );
      }

      throw error;
    }
  }
}
