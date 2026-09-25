import { ArgumentsHost, Catch, ExceptionFilter } from '@nestjs/common';
import { Response } from 'express';
import { BusinessRuleException } from './business-rule.exception';

// Maps domain business-rule violations to a JSON body `{ message }` with the
// exception's status code (422 or 409), mirroring the Laravel BusinessRuleException
// render() method.
@Catch(BusinessRuleException)
export class BusinessRuleExceptionFilter implements ExceptionFilter {
  catch(exception: BusinessRuleException, host: ArgumentsHost): void {
    const response = host.switchToHttp().getResponse<Response>();
    response.status(exception.status).json({ message: exception.message });
  }
}
