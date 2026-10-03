import { Injectable } from '@nestjs/common';
import { Dish } from '../entities/dish.entity';
import { Ingredient } from '../entities/ingredient.entity';

type IngredientWithPivot = Ingredient & {
  pivot: {
    dish_id: number;
    ingredient_id: number;
    quantity: string;
    created_at: string;
    updated_at: string;
  };
};

@Injectable()
export class DishesService {
  // EP5: ingredients via the dish_ingredients pivot. The dish row is already
  // resolved by BindDishGuard (excluded from the S3 counter). A single JOIN
  // query hydrates the same N:M relation as Eloquent's $dish->load('ingredients');
  // the generated SQL projection is ORM-specific and is reported out of band.
  async ingredients(dish: Dish): Promise<Dish> {
    const { entities, raw } = await Ingredient.createQueryBuilder('ingredients')
      .innerJoin(
        'dish_ingredients',
        'dish_ingredients',
        'ingredients.id = dish_ingredients.ingredient_id',
      )
      .addSelect('dish_ingredients.dish_id', 'pivot_dish_id')
      .addSelect('dish_ingredients.ingredient_id', 'pivot_ingredient_id')
      .addSelect('dish_ingredients.quantity', 'pivot_quantity')
      .addSelect('dish_ingredients.created_at', 'pivot_created_at')
      .addSelect('dish_ingredients.updated_at', 'pivot_updated_at')
      .where('dish_ingredients.dish_id IN (:...ids)', { ids: [dish.id] })
      .getRawAndEntities();

    dish.ingredients = entities.map((entity, index) => {
      const withPivot = entity as IngredientWithPivot;
      withPivot.pivot = {
        dish_id: raw[index].pivot_dish_id,
        ingredient_id: raw[index].pivot_ingredient_id,
        quantity: raw[index].pivot_quantity,
        created_at: raw[index].pivot_created_at,
        updated_at: raw[index].pivot_updated_at,
      };
      return withPivot;
    });

    return dish;
  }
}
