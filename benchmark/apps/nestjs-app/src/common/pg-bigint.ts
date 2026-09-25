import { types } from 'pg';

// PostgreSQL bigint (int8, OID 20) is returned as a string by node-postgres to
// avoid precision loss. All ids in this dataset are well within Number.MAX_SAFE_INTEGER,
// so we parse them as numbers to match Laravel's JSON output (numeric ids).
// COUNT(*) also returns bigint and becomes a number (pagination totals are ints);
// SUM()/AVG() return numeric (OID 1700) and remain strings, matching Eloquent's
// decimal cast which also serializes as a string.
types.setTypeParser(20, (value: string) => parseInt(value, 10));
