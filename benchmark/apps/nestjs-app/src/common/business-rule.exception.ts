// Domain business-rule violation, equivalent to Laravel's BusinessRuleException.
// The HTTP status defaults to 422 (Unprocessable Entity) and is set to 409
// (Conflict) for constraint-collision cases (e.g. overlapping reservations).
export class BusinessRuleException extends Error {
  constructor(
    message: string,
    public readonly status: number = 422,
  ) {
    super(message);
    this.name = 'BusinessRuleException';
  }
}
