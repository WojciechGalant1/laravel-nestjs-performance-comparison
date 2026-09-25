import { Body, Controller, HttpCode, Post, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { CreateReservationDto } from './dto/create-reservation.dto';
import { ReservationsService } from './reservations.service';

@Controller('reservations')
@UseGuards(JwtAuthGuard)
export class ReservationsController {
  constructor(private readonly reservationsService: ReservationsService) {}

  // EP9: POST /api/reservations
  @Post()
  @HttpCode(201)
  create(@Body() dto: CreateReservationDto) {
    return this.reservationsService.createReservation(dto);
  }
}
