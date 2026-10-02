import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BaseEntity, DataSource } from 'typeorm';
import { AppController } from './app.controller';
import { PingController } from './ping.controller';
import { AuthModule } from './auth/auth.module';
import { QueryCountLogger } from './common/query-count.logger';
import { DashboardModule } from './dashboard/dashboard.module';
import { Dish } from './entities/dish.entity';
import { Ingredient } from './entities/ingredient.entity';
import { MenuItem } from './entities/menu-item.entity';
import { Order } from './entities/order.entity';
import { OrderItem } from './entities/order-item.entity';
import { Reservation } from './entities/reservation.entity';
import { RestaurantTable } from './entities/restaurant-table.entity';
import { User } from './entities/user.entity';
import { DishesModule } from './dishes/dishes.module';
import { MenuItemsModule } from './menu-items/menu-items.module';
import { OrdersModule } from './orders/orders.module';
import { ReservationsModule } from './reservations/reservations.module';
import { TablesModule } from './tables/tables.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        type: 'postgres',
        host: config.get<string>('DB_HOST'),
        port: Number(config.get<string>('DB_PORT') ?? 5432),
        username: config.get<string>('DB_USERNAME'),
        password: config.get<string>('DB_PASSWORD'),
        database: config.get<string>('DB_DATABASE'),
        // pg Pool `max` per PM2 worker; 4 workers x 10 = 40 connections by default.
        poolSize: Number(config.get<string>('DB_POOL_SIZE') ?? 10),
        entities: [
          User,
          RestaurantTable,
          Ingredient,
          Dish,
          MenuItem,
          Reservation,
          Order,
          OrderItem,
        ],
        synchronize: false,
        // Match Eloquent's eager loading: separate SELECT ... WHERE IN per relation.
        relationLoadStrategy: 'query',
        // Route every executed query through the S3 query counter (no-op unless a
        // request carries X-Debug-Queries and has an active AsyncLocalStorage store).
        logging: ['query'],
        logger: new QueryCountLogger(),
      }),
    }),
    AuthModule,
    TablesModule,
    MenuItemsModule,
    OrdersModule,
    DishesModule,
    DashboardModule,
    ReservationsModule,
  ],
  controllers: [AppController, PingController],
})
export class AppModule {
  // Enable TypeORM's Active Record pattern: bind the initialized DataSource to
  // BaseEntity so entity static methods (find, save, createQueryBuilder, ...) work.
  constructor(dataSource: DataSource) {
    BaseEntity.useDataSource(dataSource);
  }
}
