import {
  BaseEntity,
  Column,
  CreateDateColumn,
  Entity,
  JoinTable,
  ManyToMany,
  OneToMany,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';
import { DishCategory } from './enums';
import { Ingredient } from './ingredient.entity';
import { MenuItem } from './menu-item.entity';

@Entity('dishes')
export class Dish extends BaseEntity {
  @PrimaryGeneratedColumn({ type: 'bigint' })
  id: number;

  @Column({ type: 'varchar' })
  name: string;

  @Column({ type: 'enum', enum: DishCategory, enumName: 'dish_category' })
  category: DishCategory;

  @CreateDateColumn({ name: 'created_at', type: 'timestamp' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamp' })
  updatedAt: Date;

  @OneToMany(() => MenuItem, (menuItem) => menuItem.dish)
  menuItems: MenuItem[];

  // N:M via the dish_ingredients pivot. The pivot's extra `quantity` column is
  // not exposed here (unlike Eloquent's withPivot); this keeps EP5 as a single
  // junction-joined query and is a documented minor serialization difference.
  @ManyToMany(() => Ingredient, (ingredient) => ingredient.dishes)
  @JoinTable({
    name: 'dish_ingredients',
    joinColumn: { name: 'dish_id', referencedColumnName: 'id' },
    inverseJoinColumn: { name: 'ingredient_id', referencedColumnName: 'id' },
  })
  ingredients: Ingredient[];
}
