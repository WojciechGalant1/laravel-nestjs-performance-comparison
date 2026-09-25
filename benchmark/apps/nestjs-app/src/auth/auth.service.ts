import { HttpException, Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';
import { User } from '../entities/user.entity';
import { LoginDto } from './dto/login.dto';

@Injectable()
export class AuthService {
  constructor(
    private readonly jwtService: JwtService,
    private readonly config: ConfigService,
  ) {}

  // EP10: authenticate and issue an HS256 JWT with { sub, role } claims.
  // bcryptjs.compare verifies Laravel's $2y$ bcrypt hashes directly.
  async login(dto: LoginDto): Promise<{
    access_token: string;
    token_type: string;
    expires_in: number;
  }> {
    const user = await User.createQueryBuilder('users')
      .addSelect('users.password')
      .where('users.email = :email', { email: dto.email })
      .getOne();

    if (!user || !(await bcrypt.compare(dto.password, user.password))) {
      throw new HttpException({ error: 'Unauthorized' }, 401);
    }

    const ttl = Number(this.config.get<string>('JWT_TTL') ?? 3600);
    const access_token = await this.jwtService.signAsync(
      // `sub` as a string, per RFC 7519 and matching Laravel, whose JWT library
      // serializes the subject through relatedTo(string): both tokens are identical in shape.
      { sub: String(user.id), role: user.role },
      { expiresIn: ttl },
    );

    return {
      access_token,
      token_type: 'bearer',
      expires_in: ttl,
    };
  }
}
