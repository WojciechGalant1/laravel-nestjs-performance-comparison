import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { UserRole } from '../entities/enums';
import { AuthUser } from './auth-user';

interface JwtPayload {
  sub: string;
  role: UserRole;
}

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(config: ConfigService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: config.get<string>('JWT_SECRET') as string,
      algorithms: ['HS256'],
    });
  }

  // Trusts the signed claims (sub, role) and performs no database lookup.
  // Laravel's ClaimJwtGuard does the same on protected requests; only login
  // loads the user, to verify the password.
  validate(payload: JwtPayload): AuthUser {
    return { userId: Number(payload.sub), role: payload.role };
  }
}
