import { createParamDecorator, ExecutionContext } from '@nestjs/common';
import { UserRole } from '../entities/enums';

export interface AuthUser {
  userId: number;
  role: UserRole;
}

export const CurrentUser = createParamDecorator(
  (_data: unknown, ctx: ExecutionContext): AuthUser => {
    return ctx.switchToHttp().getRequest().user as AuthUser;
  },
);
