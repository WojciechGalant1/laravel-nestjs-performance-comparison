import './common/pg-bigint';

import { RequestMethod, ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { BusinessRuleExceptionFilter } from './common/business-rule.filter';
import { QueryCountInterceptor } from './common/query-count.interceptor';
import { SnakeCaseInterceptor } from './common/snake-case.interceptor';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // All API endpoints live under /api (parity with Laravel's api.php prefix);
  // the root health route is excluded to mirror Laravel's web.php "/" route.
  app.setGlobalPrefix('api', {
    exclude: [{ path: '/', method: RequestMethod.GET }],
  });

  app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }));
  app.useGlobalFilters(new BusinessRuleExceptionFilter());
  app.useGlobalInterceptors(new QueryCountInterceptor(), new SnakeCaseInterceptor());

  await app.listen(process.env.PORT ?? 3000);
}
bootstrap();
