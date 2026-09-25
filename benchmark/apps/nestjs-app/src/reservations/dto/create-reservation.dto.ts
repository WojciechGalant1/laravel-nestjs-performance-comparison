import { Type } from 'class-transformer';
import {
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
  Matches,
  Max,
  MaxLength,
  Min,
  Validate,
  ValidatorConstraint,
  ValidatorConstraintInterface,
} from 'class-validator';

@ValidatorConstraint({ name: 'afterOrEqualToday', async: false })
class AfterOrEqualTodayConstraint implements ValidatorConstraintInterface {
  validate(value: string): boolean {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      return false;
    }

    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    return value >= today;
  }

  defaultMessage(): string {
    return 'reservation_date must be a date after or equal to today';
  }
}

export class CreateReservationDto {
  @Type(() => Number)
  @IsInt()
  table_id: number;

  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  customer_name: string;

  @IsString()
  @IsNotEmpty()
  @MaxLength(20)
  phone_number: string;

  @Matches(/^\d{4}-\d{2}-\d{2}$/)
  @Validate(AfterOrEqualTodayConstraint)
  reservation_date: string;

  @Matches(/^\d{2}:\d{2}$/)
  reservation_time: string;

  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(20)
  party_size: number;

  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(30)
  @Max(480)
  duration_minutes?: number;

  @IsOptional()
  @IsString()
  @MaxLength(1000)
  notes?: string;
}
