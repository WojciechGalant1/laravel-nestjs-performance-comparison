# 3. Materials and Methods

Following the literature analysis, this study evaluates the performance of the Laravel and NestJS frameworks within a REST API architecture. To ensure an objective comparison, two functionally equivalent applications were designed and implemented to simulate a restaurant management system. These systems were developed with a focus on architectural symmetry, utilizing standard framework solutions and minimizing the use of external libraries to isolate the overhead of the core technologies. This chapter details the experimental environment, the development of research scenarios, and the selection of performance metrics aimed at ensuring the full reproducibility of the results under controlled load conditions.

## 3.1. Study Objects

The objects of this study are two functionally equivalent backend applications developed using the Laravel (PHP) and NestJS (Node.js) frameworks. Both applications implement identical business logic in a REST API architecture, servicing a restaurant order management system.

To isolate the performance overhead of the core frameworks, both applications were built using native tools available in each framework. External libraries were strictly limited to essential libraries and packages not available natively after project initialization. Each endpoint runs the full request path of that application: routing, validation, the service layer and PostgreSQL through the ORM.

Key characteristics of the research objects:

- **Laravel** - uses a synchronous model based on PHP-FPM processes. It is a "batteries-included" framework, offering built-in solutions for ORM (Eloquent, Active Record pattern) [2, 3].
- **NestJS** - uses the event-driven model (Event Loop) of Node.js with non-blocking I/O. Its architecture is modular [11], and the data access layer is TypeORM [16].

Both applications were designed in a layered architecture (controller – service – data access), corresponding to the MVC pattern in the API layer:

- **Controller layer** - responsible for handling HTTP requests and input validation. Laravel uses Form Requests, while NestJS utilizes Data Transfer Objects (DTOs) with the class-validator library.
- **Service layer** - implementation of identical business logic (e.g. calculating order totals, checking table availability, time collision detection for reservations). 
- **Data access layer (ORM)** - Laravel uses Eloquent (Active Record), NestJS uses TypeORM configured in Active Record mode, in order to maintain architectural symmetry [15, 16]. To ensure that both ORMs follow an equivalent logical query strategy, relation eager loading is unified: Eloquent loads relations through separate queries, and TypeORM is explicitly configured with `relationLoadStrategy: 'query'` (instead of its default JOIN-based loading). The out-of-band SQL comparison verifies the number of application queries and reports the generated SQL, execution time, projections and joins separately for each ORM. The two ORMs are therefore comparable at the level of requested relations and query count, but their SQL text and exact execution plans are not assumed to be identical.
- **Authorization** - both applications implement stateless authentication using JWT tokens (HS256) with an identical claim set and the same roles (Manager, Waiter). Each token carries exactly `sub` (the user id, as the string required by RFC 7519), `role`, `iat` and `exp`, with the same secret and the same lifetime taken from a single environment variable, so the two tokens are equal in length (164 characters) and every request transmits an identically sized `Authorization` header. This required trimming the Laravel defaults: `jwt-auth` additionally emits `iss`, `nbf`, `jti` and a `prv` model hash, which have no NestJS counterpart and would have made the Laravel token roughly twice as long, so the default claim set was reduced to `iat` and `exp` and subject locking (`prv`) was disabled. On every protected request both sides verify the signature and expiry and then trust those claims: NestJS through `JwtStrategy.validate`, Laravel through a guard (`ClaimJwtGuard`) that builds the authenticated user in memory instead of the package default `SELECT` by `sub`. Neither side consults a token store (the Laravel blacklist is disabled, which also makes the `jti` claim unnecessary). The only database access on the authentication path is the credential check at login (EP10), which is outside the measured scenarios. Role checks are then applied symmetrically through Laravel Policies and the equivalent ownership checks in the NestJS order service.

Despite this unification, the ORM implementations may still generate minor differences in SQL for the same logical operation; these were accounted for in the analysis through SQL query logging. Read endpoints that traverse relations (EP2–EP5) use the unified query-based eager loading described above, while the aggregation endpoint (EP6) uses explicit JOINs with `GROUP BY` written symmetrically through the query builder in both frameworks.

Minor serialization differences exist between implementations: TypeORM returns decimal columns as strings while Eloquent returns floats; datetime formatting may differ at sub-second precision. Pagination envelopes use the same Laravel LengthAwarePaginator keys (`data`, `current_page`, `per_page`, `total`, `last_page`, `from`, `to`, `path`, `links`, and the `*_page_url` fields), with `links` windowed the same way (`onEachSide(2)`). JSON keys are emitted in snake_case in both applications. These differences do not affect the benchmark metrics (latency, throughput, error rate) as HTTP response sizes remain comparable. Response-byte sizes for EP1–EP6 are recorded during the out-of-band verification pass so that any material divergence can be corrected before the load runs.

The study uses a synthetic data model designed to simulate the complexities of a real-world restaurant system. The database schema contains 8 tables encompassing three types of relationships: one-to-many (1:N), many-to-many (N:M through a pivot table), and simple dictionary tables.

**Database tables:**

| Table | Type | Records | Relationships |
|-------|------|---------|---------------|
| `users` | dictionary | 200 | 1:N → orders |
| `tables` | dictionary | 200 | 1:N → orders, 1:N → reservations |
| `ingredients` | dictionary | 200 | N:M ↔ dishes (via dish_ingredients) |
| `dishes` | dictionary | 500 | 1:N → menu_items, N:M ↔ ingredients |
| `dish_ingredients` | pivot (N:M) | 2,000 | FK → dishes, FK → ingredients |
| `menu_items` | dictionary | 500 | 1:N → order_items, FK → dishes |
| `orders` | transactional | 100,000 | FK → tables, FK → users, 1:N → order_items |
| `order_items` | transactional | 300,000 | FK → orders, FK → menu_items |
| `reservations` | transactional | 100,000 | FK → tables |

The dataset was initialized with identical, deterministically seeded data in both application instances to ensure reproducible query results. Dictionary tables (users, tables, dishes, ingredients, menu_items) maintain fixed sizes sufficient for realistic pagination and random selection during load tests; their small size ensures that SELECT performance is dominated by framework and ORM overhead rather than database I/O. Transactional tables (orders, order_items, reservations) at 100,000 records provide a realistic workload for aggregate queries and pagination.

To keep the aggregation endpoint (EP6) meaningful and reproducible, the whole dataset is anchored to a frozen reference date supplied to both applications in a single environment variable (`BENCH_NOW`) instead of the wall clock: `orders.ordered_at` is seeded across the 90 days preceding that date, and EP6 aggregates the 30 days up to it (33,469 of the 100,000 orders). Had both the data and the window followed the wall clock, they would still have drifted apart, because the data is frozen in the database template at seeding time while the window would move every day; a measurement taken a week after seeding would then cover only 23 days of data, and two frameworks measured on different days would be compared on result sets of different sizes. With the reference date fixed, the endpoint returns a byte-identical response in both applications regardless of when the study is repeated, which was verified by comparing the two JSON payloads. Reservation records are seeded deterministically as non-overlapping time slots per table, satisfying the database-level exclusion constraint described in Section 3.3 (EP9); this guarantees that the seeded state is valid and that write-collision behaviour during load tests depends only on the request stream, not on the initial data.

Both applications share identical, independent copies of the same PostgreSQL database.

## 3.2. Research Tools

The following technology stack was used in the study:

**Application stack:**

| Component | Laravel | NestJS |
|-----------|---------|--------|
| Runtime | PHP 8.4 with PHP-FPM | Node.js 24.x LTS |
| Base container image | `php:8.4-fpm-bookworm` | `node:24-bookworm-slim` |
| Framework | Laravel 13.x | NestJS 11.x |
| ORM | Eloquent (Active Record) | TypeORM (Active Record, `relationLoadStrategy: 'query'`) |
| Authentication | php-open-source-saver/jwt-auth | @nestjs/passport + passport-jwt |
| Process manager | PHP-FPM (`pm = static`, `pm.max_children = 4`) | PM2 (cluster mode, `instances = 4`, run by `pm2-runtime`) |
| Database connections | 1 persistent connection per PHP-FPM worker (`PDO::ATTR_PERSISTENT`, 4 in total) | `pg` pool per worker, `DB_POOL_SIZE = 10` (up to 40 in total) |
| Web Server | Nginx 1.25 (reverse proxy, FastCGI to PHP-FPM) | Nginx 1.25 (reverse proxy, HTTP with keepalive) |

The use of Nginx as a reverse proxy for both applications ensures environmental symmetry, its impact on relative results is controlled and identical for both frameworks. Node.js 24.x LTS (a Long-Term Support release) was selected over the latest "Current" line to maximise reproducibility and reflect production deployment practice. NestJS serves HTTP through the Express adapter that the framework enables by default. 

Both application images are built on the same Debian 12 (bookworm) base, so the C library, OpenSSL and the kernel interface are identical and no difference can be attributed to the operating-system layer inside the container (e.g. glibc versus musl in Alpine images). Both images are multi-stage production builds without development dependencies: Laravel is installed with `composer install --no-dev` and a class map built with `--optimize` and `--classmap-authoritative`, so the autoloader does not fall back to the filesystem, and NestJS is compiled with `nest build` in a separate build stage, after which only `dist/` and the production `node_modules` are copied into the runtime image. No image contains a `.env` file; all configuration is injected by Docker Compose from a single environment file shared by both stacks, so that database credentials, the JWT secret and the token lifetime are guaranteed to be identical. Laravel's configuration and route caches (`config:cache`, `route:cache`) are generated in the container entrypoint at start-up rather than at build time, because a configuration cache built into the image would freeze the build-time environment instead of the values supplied by Compose. NestJS runs under `pm2-runtime`, which keeps the PM2 cluster in the foreground as required by the container lifecycle.

**Infrastructure:**

| Component | Version / Configuration |
|-----------|------------------------|
| Database | PostgreSQL 16 (identical schema and data for both apps) |
| Containerization | Docker + Docker Compose |
| Load generator | Apache JMeter 5.6.3 (CLI mode, own container on the Compose network) |
| Resource monitoring | `docker stats` (CPU%, memory MB) of the application, Nginx, PostgreSQL and the JMeter container |

**Choice of PostgreSQL** is motivated by the findings of Rahman et al. [6], who showed its high performance in CRUD operations compared to MySQL, particularly for UPDATE and DELETE operations.

**Choice of Apache JMeter** is based on Khlamov et al. [22], who demonstrated that JMeter outperforms Postman at high traffic levels, offering better scalability and full control over test configuration. Yenugula et al. [24] confirmed that JMeter is recommended for simulating high production loads due to its mature ecosystem and rich set of timers and monitoring plugins.

## 3.3. Operationalization of Research Hypotheses and Scenarios

This section operationalizes the three research hypotheses stated in the literature review. It defines the corresponding scenarios, endpoints, load levels, metrics and decision rules. Supplementary observations and control runs are used for interpretation and robustness, but do not replace the primary verification criteria:

**Operationalization of H1.** EP1, EP2 and EP8 represent simple data-access operations: a single-table read, a read involving at most one relation, and a simple update, respectively, with no more than 20 returned records for read endpoints. Based on the pilot, the low-load levels used for the H1 verdict are preregistered as 1 and 2 VU. Levels 4 and 10 VU are measured and reported as transition observations, but do not enter the H1 verdict. At the preregistered low-load levels, the difference in p95 response time between Laravel and NestJS is assessed with an error rate below 1% in both applications.

**Operationalization of H2.** Under high concurrency, the selected NestJS/PM2 deployment is compared with the selected Laravel/PHP-FPM deployment using the growth of p95 response time as the sole primary criterion. Error rate and the observed load region around saturation are supplementary indicators and do not determine the H2 verdict. p99 is reported at each concurrency level beside the verdict and is not an input to the slope.

**Operationalization of H3.** On the nested relation endpoint EP4, the p95 gap between Laravel and NestJS is compared with the single-table baseline EP1 at the same low-load concurrency level within S3. EP5 is a secondary many-to-many observation, while EP6 is analysed separately as a database-bound aggregation endpoint. This operationalization does not isolate ORM overhead or establish a causal mechanism.

| Hypothesis operationalization | Scenario | Endpoints | Concurrency (VU) | Verification criterion |
|------------|----------|-----------|------------------|------------------------|
| H1 | S1 – baseline / simple CRUD | EP1, EP2, EP8 | 1, 2 (primary); 4, 10 (observations) | 95% bootstrap CI of \|Δp95\| ≤ 15% at 1 and 2 VU, error rate < 1% |
| H2 | S2 – scalability / stress | EP3, EP7 (EP9 as a second write path) | 200, 500, 1000 | primary: lower p95-growth slope for NestJS; supplementary: throughput, error rate and load region around saturation; p99 reported alongside, not in the slope |
| H3 | S3 – relation complexity | EP1, EP4 (EP5 secondary, EP6 separate observation) | 1, 2, 4, 10 | at the EP1/EP4 verdict level, the lower 95% bootstrap CI of G_EP4 − G_EP1 exceeds the frozen practical threshold Y, and the consistency level has the same sign; SQL query count, response size and resource use reported |
| H3 (reinforcement) | S4 – ORM vs raw SQL (supplementary) | EP4, EP6 | the relevant S3 observation level | ORM–raw-SQL p95 difference reported separately per framework; this is the only scenario used to discuss ORM-specific overhead |

Each hypothesis is mapped to a primary measurement scenario. H3 additionally uses EP1 as an internal baseline within S3, and S4 supplements the H3 result without deciding it. EP10 (`POST /api/auth/login`) does not participate in hypothesis testing; it serves only to issue the JWT tokens consumed by the remaining scenarios. All criteria are evaluated on the median of the 10 repetitions described in Section 3.6. H1 uses the symmetric relative difference Δ = |a − b| / ((a + b) / 2), while H3 uses the absolute p95 gap in milliseconds because the latter is directly interpretable for the low-latency endpoint pair.

**Low-load rule.** For H1, the low-load set is fixed before the full S1 analysis as `{1, 2}` VU, based on the pilot. It is not recomputed from the S1 results. The throughput scaling factor X(N) / (N · X(1)), application CPU and PostgreSQL CPU are still recorded at every S1 level as load-diagnostic measures; they do not add an unregistered post-hoc inclusion rule to H1. Levels 4 and 10 VU are reported as transition observations. H3 uses a separate low-load definition for the pair (EP1, EP4); EP5 has a separate secondary observation set, while EP6 is not used to define the H3 low-load set because its aggregation is database-bound. The S1 set does not carry over to S3.

The load is generated as a closed workload: each virtual user is a JMeter thread that sends its next request as soon as the previous response arrives, without think time, so the concurrency level, not a target request rate, is the controlled variable. Each run starts with a single login (EP10) in a JMeter setUp thread group, and the resulting token is shared by all virtual users; a failed login stops the run instead of producing a series of 401 responses. Connections are kept alive between requests of the same virtual user. A request is counted as an error when it does not return the success status defined for that endpoint, or when it exceeds the 30-second timeout. Reads and the status update (EP8) succeed with HTTP 200. The two creates, EP7 and EP9, succeed with HTTP 201; a reservation collision (HTTP 409) and a validation failure (HTTP 422) are errors.

### S1: Baseline Performance and Simple CRUD (H1)

The first scenario establishes a performance baseline by measuring the frameworks' overhead under minimal query complexity. This test focuses on the response time of the routing system, middleware, and basic ORM hydration. Concurrency levels are 1, 2, 4 and 10 virtual users. The H1 verdict is evaluated at the preregistered levels 1 and 2 VU. Levels 4 and 10 VU are reported as transition observations and do not enter the H1 verdict.

The H1 verdict uses a nonparametric bootstrap (10 000 resamples, percentile method, fixed seed). In each framework × endpoint × level group, the 10 per-repetition p95 values are resampled with replacement independently, the median per group is taken, and the relative difference Δ is computed. Laravel and NestJS runs are not paired (they are independent and interleaved), so the resampling does not pair them. H1 is **rejected** when the lower CI bound of Δ exceeds 15% for at least one endpoint at at least one level of the low-load set. It is **supported** when the upper CI bound is at most 15% for all endpoints at all levels of the set, with a median error rate below 1% on both sides. Otherwise it is **inconclusive**. Throughput, Little's law mean and CPU time per request are reported beside the verdict and do not decide it.

Because H1 is evaluated separately for each endpoint, S1 is measured primarily in isolation: each of EP1, EP2 and EP8 has its own run, so that the update path of EP8 cannot influence the latency of the read endpoints. A mixed variant, in which every request picks one of the three endpoints at random, is available as a complementary measurement of the same endpoints under a shared load, with p95 still computed per endpoint. List requests address a random page within the seeded range (pages of 20 records), and EP8 updates a random existing order to a random status; neither application enforces status transitions, so every request is a valid update.

`GET /api/ping` is measured with the same runner and is not part of H1, of the mixed variant, or of any hypothesis. It passes through the same JWT check as the measured endpoints and returns a fixed JSON body without touching the database. The gap between ping and EP1 is reported as a diagnostic estimate of the additional endpoint and data-access path; it is not interpreted as a pure ORM cost.

### S2: Scalability and Stress Testing (H2)

The second scenario is designed to examine the degradation of performance as concurrency increases. The primary H2 measure is the slope of median p95 response time against concurrency. Testing is conducted at 200, 500 and 1,000 virtual users. These three preregistered levels are used for the primary regression and H2 verdict.

S2 follows the same isolation approach as S1. EP3, EP7 and EP9 are each measured in a dedicated run, so that the write-path latency of EP7 and EP9 does not inflate the response times of the read endpoint EP3. A mixed variant, in which every request picks one of the three endpoints at random, is available as a complementary measurement of the same endpoints under a shared load, with p95 still computed per endpoint.

The p95 slope is an ordinary least-squares fit of median p95 against VU on the common planned levels at or above 200 VU. EP3 is the primary S2 endpoint for the H2 verdict; EP7 and EP9 are supplementary write-path robustness checks. The slope describes the scaling of the complete selected deployment, including its application, proxy, database connection pool and database. It is not interpreted as an isolated framework or event-loop effect. The primary slope statistic is the ratio
`s_L / s_N`, where `s_L` and `s_N` are the Laravel and NestJS slopes respectively. H2 is **supported** when the lower bound of the 95% bootstrap confidence interval for this ratio exceeds 1, **rejected** when its upper bound is below 1, and otherwise **inconclusive**. The bootstrap independently resamples the 10 repetition-level p95 values within each framework × endpoint × level group, recomputes the group medians, refits both least-squares lines and recomputes the ratio. The ratio is evaluated for the primary S2 endpoint; the other isolated endpoints are reported as supplementary robustness checks. If a fitted slope is not positive or the ratio is undefined, the H2 slope verdict is inconclusive rather than being assigned a success-shaped fallback. p99 is printed at each level in the same table and is not an input to the fit.

The load-region indicators are reported separately. The descriptive **knee** is the smallest tested N at which throughput reaches at least 95% of the maximum observed throughput for that deployment. The **breakdown** level is the smallest tested N at which the median error rate exceeds 5%. If no tested level exceeds 5%, breakdown is reported as “not reached up to 1,000 VU” and treated as a right-censored observation. If only one deployment reaches breakdown, its level and the censored status of the other deployment are reported; this comparison does not receive a separate statistical verdict. When both deployments have 0% errors at all levels, the error-rate comparison is reported as a tie/not applicable and neither supports nor rejects H2. Throughput, error rate, knee and breakdown are not substituted for the slope criterion. Application CPU, PostgreSQL CPU, memory, pool size and other resource measurements are reported alongside the slope so that a database- or infrastructure-bound region is not misattributed to the framework.

To ensure that the write-heavy endpoints actually measure write throughput rather than rejection paths, their business logic was designed to remain valid under sustained concurrent load. EP7 always contains exactly one order item in the request body. Both applications perform the same data operations in the same order: existence of the table, availability of the referenced menu item, insertion of one order, insertion of one order item, and update of the order total, all inside one transaction. Database validation is implemented in the service layer rather than by framework-specific request rules, so the logical reads are the same on both sides. Transaction-control statements (`BEGIN`/`START TRANSACTION` and `COMMIT`) and ORM-specific response hydration are reported separately as implementation overhead; they are not treated as additional business operations. The reservation endpoint (EP9) enforces time-slot uniqueness through a database-level exclusion constraint (`EXCLUDE USING gist`, see below) rather than an application-level read-then-write check, which both eliminates the race condition under concurrency and makes collision handling atomic and identical across both frameworks. Both applications catch the resulting constraint-violation error and translate it into the same domain response.

Because the two stacks differ in the number of database connections available under load (4 for PHP-FPM, up to 40 for NestJS, see Section 3.4), S2 includes a control run that isolates this factor. At the concurrency levels at which saturation is observed in the main runs, S2 is repeated for NestJS with `DB_POOL_SIZE = 1`, i.e. one connection per PM2 worker and 4 connections in total, matching PHP-FPM. If the NestJS advantage disappears once the connection count is equalised, the H2 result is attributed to connection pooling; if it persists, it is attributed to the non-blocking I/O model. The control run is reported alongside the main S2 results and does not replace them. A plateau that appears in both frameworks is interpreted separately from H2: once container limits are equalised, throughput can stop growing with concurrency because of contention inside the database rather than because the application layer is saturated [25], and such a result is reported as a database-side limit.

### S3: Relation Complexity (H3)

Scenario S3 measures whether relation traversal increases the observed performance gap between Laravel and NestJS relative to the single-table baseline. EP4 is the primary relation-heavy endpoint and EP5 is a secondary many-to-many observation. EP6 runs explicit JOINs with aggregation and is analysed separately as a database-bound observation; it does not decide H3. EP1 is measured inside S3 at the same concurrency levels, so the baseline comes from the same scenario. The planned levels are 1, 2, 4 and 10 virtual users. The pilot indicates that 2 VU is the appropriate primary verdict level: at 4 VU EP1 approaches the Laravel CPU limit and EP6 approaches the PostgreSQL limit. Levels 4 and 10 VU remain exploratory observations.

For each endpoint k, the primary metric is the absolute p95 gap:

```
G_k = |p95_L(k) − p95_N(k)|
D = G_EP4 − G_EP1
```

All p95 values are medians of 10 repetitions of S3 at the same VU. D is measured in milliseconds; positive values mean that the absolute framework gap is larger for EP4 than for EP1. The primary H3 criterion is evaluated for EP4 at 2 VU. EP5 is reported separately using the same metric, but does not replace EP4 as the primary endpoint. EP6 is reported with p95, throughput, CPU, PostgreSQL CPU, SQL query count and response size, without entering the H3 verdict. The hypothesis concerns the combined effect of relation access, ORM hydration, SQL generation, database execution and response serialization; it does not isolate ORM overhead or establish a causal mechanism. Relation-loading strategy is equalised in Section 3.1.

The ratio of median p95 (Laravel / NestJS) is reported per endpoint as a secondary figure. Response size in bytes and SQL query count are reported beside the gaps because a larger payload or a different number of statements can explain part of the observed difference. Neither measure is treated as a post-hoc adjustment to D.

**Verdict and consistency levels.** EP4 is evaluated at 2 VU, with 1 VU as the consistency level. EP5 uses the same levels as a secondary observation. If the pair fails the low-load rule at 2 VU, the endpoint is reported as not evaluable for the primary criterion rather than moving the verdict to a higher load. Levels 4 and 10 VU are observations only. S4 uses the corresponding S3 observation level and is the only scenario used to discuss ORM-specific overhead.

**Threshold Y**, frozen after S1 and before S3. For each level v in the S1 low-load set, s(v) = sqrt(SD_L(v)² + SD_N(v)²), where SD_L and SD_N are the standard deviations of the 10 per-repetition EP1 p95 values of each framework in S1. Then Y = max(2 ms, 2 · max_v s(v)). The 2 ms floor follows from JMeter's 1 ms p95 resolution. Using the run-level SD makes Y conservative. Using the maximum over the S1 low-load levels removes dependence on the S3 verdict level, which is unknown at freeze time. `scripts/summarize.py --freeze-h3-threshold` writes `results/h3_threshold.json`. The H3 table refuses to run without that file.

**H3 verdict.** H3 is supported when, at EP4's 2-VU verdict level, the lower bound of the 95% bootstrap CI of D exceeds Y and D has the same sign at the 1-VU consistency level. It is rejected when the upper CI bound is below Y at 2 VU, and inconclusive otherwise. EP5 is reported as a secondary result and does not override the EP4 verdict. EP6 is not evaluable for H3 and does not decide it. The CI resamples the four groups (framework × {EP1, EP4}) independently, 10 000 times, using the percentile method and the same fixed seed as H1.

To make the number of emitted SQL statements an observable, verifiable metric rather than an assumption, both applications expose a lightweight diagnostic that counts the queries produced per request. The counter is triggered exclusively by the presence of an `X-Debug-Queries` request header, so it is completely inert on benchmark traffic (JMeter load requests omit the header) and adds no overhead to the measured runs. In Laravel this is implemented as a middleware placed *after* `auth:api`, which enables `DB::getQueryLog()` for the request; because authentication issues no SQL (the user is taken from the signed claims) and route-model binding is resolved earlier in the pipeline, the reported figure reflects purely the controller/ORM hydration queries. The count is returned in an `X-Query-Count` response header and the exact SQL statements are written to the application log for inspection. NestJS provides an equivalent interceptor over the TypeORM logger. A single instrumented request per endpoint is issued out-of-band (before or after the load run) to record the query count, confirming for example that EP4’s three-level eager load resolves as a fixed set of `SELECT ... WHERE ... IN (...)` statements (one per relation) with no N+1 pattern, and that EP5/EP6 collapse to a single join/aggregation query. This lets the study report the query count symmetrically for both frameworks.

### S4: ORM vs Raw SQL (supplementary reinforcement of H3)

To further isolate the overhead introduced by the Active Record abstraction — deliberately used on both sides, through Eloquent in Laravel and through TypeORM entities bound to `BaseEntity` in NestJS — a supplementary scenario compares the ORM-generated queries against hand-optimized raw SQL. EP4 and EP6 are additionally implemented using the native database drivers (`DB::select` in Laravel and `query()` in NestJS) to determine the share of latency attributable solely to the ORM layer. S4 is run at the H3 verdict level of the corresponding endpoint (EP4 at EP4's verdict level, EP6 at EP6's verdict level; both known only after S3). If EP6 is not evaluable in S3, S4 for EP6 is omitted or reported as an observation at 1 VU and does not supplement the H3 verdict. S4 does not carry a hypothesis of its own: H3 is falsifiable through D = G_EP4 − G_EP1 in S3, and S4 is therefore reported as a supplementary result that quantifies the absolute cost of the ORM within each framework separately.

### Reservation integrity constraint (EP9)

To remove the read-then-write race condition inherent in application-level overlap detection, time-slot uniqueness for reservations is enforced directly in PostgreSQL using a GiST exclusion constraint. The `btree_gist` extension is enabled so that equality on `table_id` can be combined with range overlap detection on the reservation interval:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE reservations
  ADD CONSTRAINT reservations_no_overlap
  EXCLUDE USING gist (
    table_id WITH =,
    tsrange(
      (reservation_date + reservation_time),
      (reservation_date + reservation_time + make_interval(mins => duration_minutes))
    ) WITH &&
  )
  WHERE (status <> 'cancelled');
```

Both applications simply attempt the insert and translate a constraint violation (`SQLSTATE 23P01`, exclusion_violation) into an identical domain error. Because the database guarantees atomicity, the two frameworks exhibit identical correctness semantics under concurrency, and the only thing being measured at EP9 is the cost of the insert path itself.


### Endpoint complexity summary

The "Data-access complexity" column describes the logical relational depth of each endpoint. For relation-traversing read endpoints (EP2–EP5) this is realised through the unified query-based eager loading (separate `SELECT ... WHERE IN` statements) in both frameworks; only EP6 uses explicit SQL JOINs with aggregation. All read scenarios are executed using a JWT token with the Manager role, so that role-based query scopes (e.g. the order list at EP3, which is filtered to the authenticated waiter's own orders but unrestricted for managers) return a deterministic, identically sized result set across both frameworks.

| Endpoint | Method | Data-access complexity | Scenario |
|----------|--------|------------------------|----------|
| EP1: `/api/tables` | GET | baseline (no relations) | S1, S3 |
| EP2: `/api/menu-items` | GET | 1 relation (eager) | S1 |
| EP3: `/api/orders` | GET | 2 relations (eager) | S2 |
| EP4: `/api/orders/{id}` | GET | 3-level nested eager load | S3, S4 |
| EP5: `/api/dishes/{id}/ingredients` | GET | N:M via pivot | S3 |
| EP6: `/api/dashboard/summary` | GET | 3 JOIN + aggregation | S3, S4 |
| EP7: `/api/orders` | POST | transactional insert (order + items) | S2 |
| EP8: `/api/orders/{id}/status` | PATCH | simple UPDATE | S1 |
| EP9: `/api/reservations` | POST | insert + DB exclusion constraint | S2 |
| EP10: `/api/auth/login` | POST | authentication | setup |
| `/api/ping` | GET | no database access | diagnostic, not in H1 |

## 3.4. Research Stand

The experiments were conducted in a unified Docker container environment, which ensures resource isolation and eliminates the influence of operating system configuration on results [7, 14].

**Host and container specification:**

| Parameter | Value |
|-----------|-------|
| Host processor | 12 vCPU |
| Host RAM | 15.6 GiB available to the virtual machine |
| Host operating system | Ubuntu 22.04.5 LTS on WSL2 (kernel 6.6.87, Windows host) |
| Application container | 4 CPUs, 2 GB RAM (identical for both frameworks) |
| Nginx container | 1 CPU, 256 MB RAM |
| PostgreSQL container | 4 CPUs, 2 GB RAM |
| Load generator | JMeter 5.6.3 in a container on the same host, without CPU or memory limits |

The distinction between the host and the container limits matters for the interpretation of the results. The frameworks are compared under a 4-CPU budget, which is the quantity that `pm.max_children = 4` and the four PM2 workers are matched to, while the remaining host cores absorb JMeter and the operating system, so the load generator does not compete for the CPU budget under measurement. Because the limit is a CPU quota rather than a fixed set of pinned cores, a residual influence of host load cannot be ruled out entirely; it is mitigated by running the load generator and the measured stack as the only active workloads and by reporting the median of ten repetitions (Section 3.6).

Each framework runs in its own container with identical, explicitly declared resource limits (CPU, memory). Tofan [25] identified the lack of such equalisation as a weakness of earlier comparisons, because observed differences then reflect uneven CPU and memory allocation as much as the systems under test. Both applications connect to the same PostgreSQL instance but use separate databases with identical schemas and data.

The environment is defined in a single Docker Compose file. Each application stack consists of the application container (PHP-FPM or PM2) and a dedicated `nginx:1.25` container: for Laravel, Nginx forwards every request over FastCGI to the front controller (`public/index.php`), and for NestJS it proxies HTTP to the Node.js cluster over persistent upstream connections (`keepalive`, HTTP/1.1). Both Nginx configurations disable access logging, and both use the same image and therefore the same worker settings, so the proxy layer adds no asymmetric logging or I/O cost. The two stacks are placed behind separate Compose profiles and only one is running during a measurement, so the frameworks never compete for the same vCPUs; PostgreSQL 16 runs continuously in both cases. Resource limits are read from the shared environment file and are identical for both stacks: the application container is limited to 4 CPUs and 2 GB of memory, each Nginx container to 1 CPU and 256 MB, and PostgreSQL to 4 CPUs and 2 GB. The PostgreSQL data directory is kept in a named Docker volume rather than a bind mount, because on WSL2 a bind mount onto the Windows file system would slow down database I/O and add noise unrelated to either framework.

JMeter 5.6.3 runs in non-GUI mode in its own container, attached to the same Compose network and started for each run. It addresses the stack under test by service name (`laravel-nginx` or `nestjs-nginx`, port 80) rather than through the ports published on the host, so the load does not pass through the Docker Desktop and WSL port forwarding, which would add latency and variance unrelated to either framework. The JMeter container has no CPU or memory limit, so it draws on the host cores outside the 4-CPU application budget, and the same image, test plan and property files are used for both frameworks.

The number of database connections differs between the stacks by design. A PHP-FPM worker handles one request at a time and holds a single connection, so Laravel uses at most 4 connections. By default Laravel opens a new connection for every request, so each request would also pay for the TCP handshake, SCRAM-SHA-256 authentication and the start of a new PostgreSQL backend process (about 7.5 ms per request in this environment, compared with about 0.4 ms for a query over an open connection). Persistent PDO connections (`PDO::ATTR_PERSISTENT`) are therefore enabled, so that each worker keeps its connection open across requests in the same way as the Node.js pool; otherwise the comparison would measure connection setup rather than the frameworks. A Node.js worker handles many requests concurrently and draws connections from a `pg` pool, whose size is set explicitly through `DB_POOL_SIZE` (10 per worker, the `pg` default, giving up to 40 connections). This asymmetry is not a configuration artefact but a direct consequence of the two concurrency models under study, and it is therefore kept in the main measurements. To make it an explicit, controlled parameter rather than a hidden default, its influence on H2 is measured separately in the S2 control run with `DB_POOL_SIZE = 1` (Section 3.3).

To ensure a fair comparison of CPU utilization, both frameworks were configured to utilize all available vCPU cores equally. PHP-FPM was set to static process management with `pm.max_children = 4`, matching the number of available virtual cores. NestJS was launched using PM2 in cluster mode with 4 worker instances. Both configurations represent standard production-style deployments for their respective ecosystems and ensure that neither framework has an inherent single-process resource advantage. Without this symmetry, PHP-FPM would utilize all four cores by default while a single Node.js process would be limited to one, giving Laravel a fourfold resource advantage that would confound the scalability hypothesis (H2) and make it a deployment artefact. Nginx sits in front of both process pools as a uniform HTTP entry point with a single upstream in each case. Requests compete for the shared PHP-FPM listening socket and are accepted by available PHP-FPM workers; on the NestJS side, the PM2 cluster master distributes connections among the four Node.js workers. The two mechanisms are intentionally different and are treated as part of the selected deployments.

The PostgreSQL server settings are pinned explicitly in the Compose file at the PostgreSQL 16 defaults (`max_connections = 100`, `shared_buffers = 128MB`, `work_mem = 4MB`, `effective_cache_size = 4GB`), so that an image update cannot silently change the conditions between measurement series and so that the connection ceiling is a documented value. Since 100 is well above both the 40 connections NestJS can open and the 4 of PHP-FPM, the server-side connection limit is never reached and can be excluded as a cause of the saturation observed in S2.

## 3.5. Metrics

The following metrics are collected for each scenario:

| Metric | Description | Collection method |
|--------|-------------|-------------------|
| **Response time** | Median (p50), 95th percentile (p95), 99th percentile (p99), nearest-rank method, per endpoint | JMeter results file (JTL), `scripts/summarize.py` |
| **Throughput** | Successful requests per second (RPS) over the steady-state window | JMeter results file (JTL) |
| **Error rate** | Percentage of requests that did not return the expected success status (HTTP 200 for reads and EP8, HTTP 201 for EP7 and EP9) or exceeded the 30-second timeout. HTTP 409 and 422 on write endpoints are counted as errors. In S2 this is a secondary saturation indicator. | JMeter results file (JTL) |
| **CPU usage** | Mean and peak CPU of the application container, also as a share of its 4 allocated CPUs. Mean CPU of Nginx, PostgreSQL and JMeter is recorded in the same stream; PostgreSQL share of its own 4-CPU limit enters the low-load rule | `docker stats`, sampled about every 0.5 s |
| **Memory usage** | Mean and peak RAM of the application container (MiB) | `docker stats` |
| **Mean response time (secondary)** | Little's law mean, concurrency divided by throughput. Independent of JMeter rounding elapsed times to whole milliseconds. Not an input to H1–H3 | Derived in `scripts/summarize.py` |
| **CPU time per request (secondary)** | Application CPU, as a fraction of one core, divided by throughput. Not an input to H1–H3 | `docker stats` and throughput |
| **G_k / D (H3)** | Absolute p95 gap, G_k = \|p95_L − p95_N\|, for EP1 and EP4; D = G_EP4 − G_EP1 in milliseconds, with a 95% bootstrap CI. EP5 is reported separately and EP6 is a database-bound observation. | `scripts/summarize.py` |
| **Response size (secondary)** | Response body size in bytes, reported beside H3 to distinguish relational work from payload-size effects | JMeter verification pass |
| **SQL query count** | Number of SQL queries generated per request (S3 only) | Header-triggered diagnostic (`X-Debug-Queries` → `X-Query-Count`); Laravel `DB::getQueryLog()` / NestJS TypeORM logger |

The focus on percentiles (p95, p99) rather than mean response time allows analysis of tail latency - the behavior of the system under worst-case conditions, which is critical for real-world user experience and is often masked by arithmetic mean [21, 23, 25]. JMeter records elapsed time in whole milliseconds, which is coarse when a response takes about 2 ms. The two secondary figures above keep that from being the only view of the service cost: Little's law mean uses the request count and the wall-clock window, and CPU time per request uses the container's CPU. When latency rises while CPU time per request stays flat, the rise is queueing in front of the workers. Neither figure decides a hypothesis.

## 3.6. Experimental Procedure

Each test is conducted following a rigorous protocol to ensure reproducibility:

1. **Warm-up phase** - each repetition is preceded by a 2-minute warm-up run with the same endpoint and concurrency level, whose results are discarded, to stabilize JIT mechanisms (Node.js V8 TurboFan) and OPcache (PHP). Kuffel and Walter [10] observed that the median latency of Node.js applications falls during the first seconds under constant load, attributing the change to V8 optimizations, so that interval is excluded from the reported steady state. Both applications are run with production-grade optimizations enabled symmetrically: Laravel uses OPcache (with JIT enabled), configuration caching (`config:cache`) and route caching (`route:cache`), while NestJS is executed from a compiled production build (`nest build`). This guarantees that the warm-up measures steady-state runtime behaviour rather than first-request compilation cost.
2. **Execution** - the actual measurement runs for the duration specified per scenario (3–5 minutes of steady state; 3 minutes in S1). The first 10 seconds, during which the virtual users are started, are excluded from all metrics, and CPU and memory samples are cut to the same window.
3. **Repetitions** - each test is repeated 10 times. Final results are presented as the median and standard deviation of the obtained samples, which allows elimination of outliers and assessment of measurement stability.
4. **Isolation** - before each new scenario (and before each of the 10 repetitions), a single script (`scripts/db-reset.sh`) restores the database to its initial state and restarts the application and Nginx containers of the stack under test, eliminating data mutation artifacts as well as in-process state (OPcache and JIT in PHP, V8 warm-up and the connection pool in Node.js); the script restarts only the stack that is running and warns if both are up at once. For state-changing endpoints, the database is restored again after the warm-up and immediately before the measurement, so the two frameworks start the measured window with the same row counts and sequence values even when their warm-up throughput differs. This second restore does not rebuild application caches; the application and database connections are restarted as part of the reset. Dictionary tables (`users`, `tables`, `dishes`, `ingredients`, `menu_items`) are read-only during the tests; only the transactional tables (`orders`, `order_items`, `reservations`) are mutated, by EP7, EP8 and EP9. Restoration is performed by dropping the working database and recreating it from a PostgreSQL template that was cloned from the seeded snapshot (`DROP DATABASE nestjs_app; CREATE DATABASE nestjs_app TEMPLATE nestjs_app_template;`, and the analogous pair for `laravel_app`). This restores sequences as well as row data and is substantially faster than re-running the seeder. The template databases themselves are created once, after the initial seed of `laravel_app` and its copy into `nestjs_app` (`CREATE DATABASE nestjs_app TEMPLATE laravel_app`). Both steps are executed with `psql` inside the PostgreSQL container, so the procedure does not depend on client tools installed on the host.
5. **Automation** - the whole sequence (reset and restart, warm-up, measurement with resource sampling) is executed by a single script (`scripts/run-scenario.sh`). The main series is run as `scripts/run-scenario.sh both <scenario>`: the repetition is the outer loop and the framework the inner loop, with the order of Laravel and NestJS shuffled from a fixed seed within each repetition, so the comparison is not confounded with thermal or host drift. Only one application stack runs at a time. Each repetition stores the raw JMeter samples, the `docker stats` trace (including the JMeter container), the post-run row counts of `orders`, `order_items` and `reservations`, and a metadata file with the run parameters, the interleave seed and the realised framework order. `scripts/summarize.py` derives all reported metrics from these files, so every figure can be recomputed from the raw data.

A single-repetition pilot (n = 1; 60 s warm-up, 60 s measurement) was run to check the load-level design before the main series. It showed that throughput and CPU scale almost linearly at 1–4 concurrent users with no error, while at 10 users the stacks approach saturation. Based on the pilot and on an analysis of the criteria, four design changes were made before S1: (i) the S1 levels were changed from 10 and 50 to 1, 2, 4 and 10, and the term "low load" was operationalized by a formal rule (Section 3.3); (ii) the baseline for H3 was moved into S3 (EP1 measured at the same levels), because the previous criterion used a baseline from another scenario and an unattainable bound; (iii) H3 was narrowed to EP4 as the primary relation endpoint, with EP5 as a secondary observation and EP6 as a separate database-bound observation; (iv) the H3 metric was changed to the absolute p95-gap difference D = G_EP4 − G_EP1, with a threshold frozen after S1 and before S3. The H1 hypothesis and its 15% threshold were not changed. The pilot data are not included in the results.