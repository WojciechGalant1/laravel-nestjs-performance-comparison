export enum UserRole {
  Manager = 'manager',
  Waiter = 'waiter',
}

export enum TableStatus {
  Available = 'available',
  Occupied = 'occupied',
  Reserved = 'reserved',
  Cleaning = 'cleaning',
}

export enum DishCategory {
  Starter = 'starter',
  Main = 'main',
  Dessert = 'dessert',
  Drink = 'drink',
  Side = 'side',
}

export enum ReservationStatus {
  Pending = 'pending',
  Confirmed = 'confirmed',
  Cancelled = 'cancelled',
}

export enum OrderStatus {
  Open = 'open',
  Paid = 'paid',
  Cancelled = 'cancelled',
}

export enum OrderItemStatus {
  Pending = 'pending',
  InProgress = 'in_progress',
  Completed = 'completed',
  Cancelled = 'cancelled',
}
