# 3. Materials and Methods

Following the literature analysis, this study evaluates the performance of the Laravel and NestJS frameworks within a REST API architecture. To ensure an objective comparison, two functionally equivalent applications were designed and implemented to simulate a restaurant management system. These systems were developed with a focus on architectural symmetry, utilizing standard framework solutions and minimizing the use of external libraries to isolate the overhead of the core technologies. This chapter details the experimental environment, the development of research scenarios, and the selection of performance metrics aimed at ensuring the full reproducibility of the results under controlled load conditions.

## 3.1. Study Objects

The objects of this study are two functionally equivalent backend applications developed using the Laravel (PHP) and NestJS (Node.js) frameworks. Both implement identical restaurant-order business logic in a REST API architecture. To isolate framework overhead, they use native framework tools and only essential external packages; each endpoint includes the complete request path from routing and validation through the service layer and PostgreSQL access via the ORM.

Key characteristics of the research objects:

- **Laravel** - uses a synchronous model based on PHP-FPM processes. It is a "batteries-included" framework, offering built-in solutions for ORM (Eloquent, Active Record pattern) [2, 3].
- **NestJS** - uses the event-driven model (Event Loop) of Node.js with non-blocking I/O. Its architecture is modular [11], and the data access layer is implemented using TypeORM [16].

Both applications were designed in a layered architecture (controller – service – data access), corresponding to the MVC pattern in the API layer:

- **Controller layer** - handles HTTP requests and input validation. Laravel utilizes Form Requests, while NestJS uses Data Transfer Objects (DTOs) with the `class-validator` library. Database-dependent validations are performed explicitly in the service layer in both applications.
- **Service layer** - implements identical business logic (e.g., calculating order totals and validating referenced entities).
- **Data access layer (ORM)** - Laravel uses Eloquent, while NestJS uses TypeORM in Active Record mode. Relation loading is unified: Eloquent uses separate queries by default, and TypeORM is explicitly configured with `relationLoadStrategy: 'query'` instead of JOINs.
- **Authentication and authorization** - both applications use stateless JWT authentication (HS256) with identical claims (`sub`, `role`, `iat`, `exp`), secret, and expiration time, resulting in an identical 164-character token. Signature and expiry are verified in-memory without database or token-store lookups.

To ensure architectural symmetry, framework-specific defaults were adjusted across layers. Relation-traversing read endpoints (EP2–EP5) apply the unified query-based eager loading, while the aggregation endpoint (EP6) utilizes explicit JOINs with `GROUP BY` written via the query builder in both frameworks. Although minor SQL formatting differences may remain, the logical query strategy is unified to yield an equivalent number of database requests per endpoint.

Both applications return identical response structures using Laravel's paginator envelope and `snake_case` keys. Minor scalar formatting differences—such as TypeORM returning decimal columns as strings versus floats in Eloquent, or sub-second datetime formatting—are treated as inherent characteristics of the measured framework paths.

The study uses a synthetic data model designed to simulate the complexities of a real-world restaurant system. The database schema contains 8 tables classified into three categories (dictionary, pivot, transactional) linked by 1:N and N:M relationships.

**Database tables:**

| Table | Type | Records | Relationships |
|-------|------|---------|---------------|
| `users` | dictionary | 200 | 1:N → orders |
| `tables` | dictionary | 200 | 1:N → orders |
| `ingredients` | dictionary | 200 | N:M ↔ dishes (via dish_ingredients) |
| `dishes` | dictionary | 500 | 1:N → menu_items, N:M ↔ ingredients |
| `dish_ingredients` | pivot (N:M) | 2,000 | FK → dishes, FK → ingredients |
| `menu_items` | dictionary | 500 | 1:N → order_items, FK → dishes |
| `orders` | transactional | 100,000 | FK → tables, FK → users, 1:N → order_items |
| `order_items` | transactional | 300,000 | FK → orders, FK → menu_items |

The dataset is initialized deterministically in separate databases created from a single seeded PostgreSQL template. Because the entire dataset fits within the allocated database container RAM, measurements are dominated by framework execution rather than disk I/O. The transactional tables provide a realistic workload for aggregation and pagination.

To guarantee byte-identical responses for EP6 across repeated runs, the dataset is anchored to a frozen reference date (`BENCH_NOW`). The `orders.ordered_at` field spans the 90 days preceding this date, with EP6 aggregating the final 30-day window (33,469 of the 100,000 orders).

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

The use of Nginx as a reverse proxy for both applications ensures environmental symmetry; its impact on relative results is controlled and identical across frameworks. Node.js 24.x LTS was selected over the "Current" release line to maximize reproducibility and align with production deployment standards. NestJS serves HTTP traffic through its default Express adapter.

Both application images share an identical Debian 12 (bookworm) base, ensuring identical C libraries, OpenSSL versions, and kernel interfaces. To isolate production runtime performance, both stacks use multi-stage builds excluding development dependencies. Laravel is configured with optimized classmaps (`--classmap-authoritative`), while NestJS is executed from a pre-compiled build stage.

Runtime configurations are injected exclusively via Docker Compose from a single shared environment file, guaranteeing identical database credentials, JWT secrets, and token lifetimes. To allow dynamic environment injection at startup, Laravel's configuration and route caches (`config:cache`, `route:cache`) are generated in the container entrypoint rather than during image construction.

**Infrastructure:**

| Component | Version / Configuration |
|-----------|------------------------|
| Database | PostgreSQL 16 (identical schema and data for both apps) |
| Containerization | Docker + Docker Compose |
| Load generator | Apache JMeter 5.6.3 (CLI mode, own container on the Compose network) |
| Resource monitoring | `docker stats` (CPU%, memory MB) of the application, Nginx, PostgreSQL, and the JMeter containers |

The selection of PostgreSQL is motivated by the findings of Rahman et al. [6], who demonstrated its superior CRUD performance compared to MySQL, particularly for write and update operations.

Apache JMeter was selected as the load generator based on Khlamov et al. [22], who showed that JMeter outperforms Postman under high traffic conditions by offering superior scalability and fine-grained execution control. This choice is further supported by Yenugula et al. [24], who recommend JMeter for high-concurrency production load simulation due to its mature ecosystem and comprehensive monitoring integration.

## 3.3. Operationalization of Research Hypotheses and Scenarios

This section operationalizes the research hypotheses into measurable experimental scenarios (S1–S3). The table below summarizes the alignment between each hypothesis, its primary scenario, targeted endpoints, load levels, metrics, and decision rules.

| Hypothesis operationalization | Scenario | Endpoints | Concurrency (VU) | Verification criterion |
|------------|----------|-----------|------------------|------------------------|
| H1 | S1 – baseline / simple CRUD | EP1, EP2, EP8 | 1, 2 (primary); 4, 10 (observations) | upper bound of the 95% bootstrap CI of \|Δp95\| ≤ 15% for all endpoints at both verdict levels, median error rate < 1% |
| H2 | S2 – scalability / stress | EP3, EP7 | 200, 500, 1000 | primary: lower p95-growth slope for NestJS; supplementary: throughput, error rate and resource use; p99 reported alongside, not in the slope |
| H3 | S3 – relation complexity | EP1, EP4 (EP5 secondary, EP6 separate observation) | 1, 2, 4, 10 | at the EP1/EP4 verdict level, the lower 95% bootstrap CI of D = S_EP4 − S_EP1 exceeds 2 ms and D is positive at the consistency level; SQL query count, response size and resource use reported |

Each hypothesis is mapped to a primary measurement scenario. H3 additionally uses EP1 as an internal baseline within S3. EP10 (`POST /api/auth/login`) does not participate in hypothesis testing; it serves only to issue the JWT tokens consumed by the remaining scenarios. All criteria are evaluated on the median of the 10 repetitions described in Section 3.6. H1 uses the symmetric relative difference Δ = |a − b| / ((a + b) / 2), while H3 uses a signed p95 contrast in milliseconds.

**Low-load validity rule.** Verdict levels are fixed in advance (H1: 1 and 2 VU; H3: 2 VU, with 1 VU as the consistency level). A fixed level is valid for a verdict only if, for both frameworks and every endpoint entering that verdict, (a) the throughput scaling factor X(N) / (N · X(1)) is at least 0.80, (b) the mean CPU of the application container is below 80% of its limit (320% in docker-stats units, where 100% is one core), and (c) the mean CPU of the PostgreSQL container is below 80% of its limit. All quantities are medians over the repetitions, and X(1) comes from the same scenario. If a level is not valid, the H1 verdict is evaluated at the remaining level (and this is reported), whereas H3 is reported as not evaluable. Higher levels are reported as observations and never enter a verdict. The thresholds are fixed before the main series.

**Bootstrap procedure.** Confidence intervals for the H1 and H3 contrasts are obtained from 10,000 independent percentile bootstrap resamples of the relevant framework/endpoint groups, using a fixed seed. The precise contrast and decision rule are specified with each hypothesis; the bootstrap interval is reported together with the point estimate.

### S1: Baseline Performance and Simple CRUD (H1)

Scenario S1 measures the response time of the full request path (Nginx, routing, JWT verification, validation, service layer, ORM, and PostgreSQL) for three simple operations: a single-table read (EP1), a read with one relation (EP2), and a simple update (EP8). Each endpoint is measured in an isolated run at 1, 2, 4, and 10 virtual users to prevent write side effects from affecting read latency.

**Verdict levels.** The H1 verdict is evaluated at 1 and 2 VU, which were fixed before the main series based on the single-repetition pilot (Section 3.6). The low-load validity rule (Section 3.3) is applied to these levels as a check: if 2 VU fails the rule, the verdict is evaluated at 1 VU alone; if 1 VU fails, H1 is not evaluable. Levels 4 and 10 VU serve strictly as transition observations and never enter the verdict.

**Request streams.** List requests query random pages within the seeded range (20 records per page), while EP8 updates random existing orders. Input parameters are drawn from a fixed, pre-generated seed file shared across frameworks to guarantee identical request sequences. EP8 performs an unconditional status update in both applications (performing an explicit DB write regardless of whether the status value changed) without enforcing state transitions, ensuring all requests are valid.

**Verdict rule.** The relative difference Δ in p95 response time is evaluated for each endpoint at valid verdict levels using independent bootstrap resampling across interleaved runs (Section 3.3). H1 is **rejected** if the lower bound of the 95% CI of Δ exceeds 15% for any endpoint at any verdict level. It is **supported** if the upper bound of Δ is at most 15% across all endpoints and verdict levels, provided the median error rate remains below 1% in both frameworks. Otherwise, the result is **inconclusive**. Because p95 values are recorded in 1-ms increments, secondary metrics (p95 ratio, Little's-law mean, CPU time per request) are reported alongside for diagnostic precision but do not decide the verdict.

`GET /api/ping` is measured at 1 and 2 VU (5 repetitions) as a diagnostic baseline. It executes JWT verification and returns a fixed JSON payload without database access. The latency gap between `/api/ping` and EP1 provides a diagnostic estimate of the additional data-access path overhead, though it is not interpreted as an isolated ORM cost.


### S2: Scalability and Stress Testing (H2)

Scenario S2 evaluates performance degradation under high concurrency across three preregistered load levels: 200, 500, and 1,000 virtual users. Following the emphasis on tail latency in resource-constrained environments [25], the primary measure for H2 is the growth rate (slope) of median p95 response times. To prevent write latency from confounding read metrics, the primary read endpoint (EP3) and the transactional write endpoint (EP7) are measured in separate, isolated runs.

**Verdict rule.** Let $S_k = p95_L(k) - p95_N(k)$ represent the median p95 latency difference between frameworks for endpoint $k$. The primary test statistic is the signed contrast:
$$D = S_{\text{EP4}} - S_{\text{EP1}}$$
expressed in milliseconds. H3 is **supported** if the lower bound of the 95% bootstrap confidence interval of $D$ at 2 VU exceeds the fixed practical threshold of 2 ms (twice the 1-ms measurement resolution of JMeter) and the point estimate of $D$ at 1 VU remains positive. Otherwise, H3 is **not supported** (or **not evaluable** if the low-load validity rule fails at 2 VU). A negative $D$ cannot support H3. In all cases, $D$ and its 95% CI are reported, allowing the reader to distinguish a near-zero, small, or reversed effect. This signed contrast specifically tests the directional claim that relation complexity increases Laravel's disadvantage, rather than a non-directional expansion of absolute gap magnitude.

Secondary metrics—including p99 latency, throughput, error rates, CPU/memory consumption, and database connection usage—are reported alongside the slope to prevent misattributing database- or infrastructure-bound saturation solely to framework overhead.

**Connection-pool sensitivity control.** Because the two deployment stacks differ in database connection capacity under load (4 static connections for PHP-FPM vs. up to 40 for NestJS, Section 3.4), S2 includes a control run to evaluate connection-pool sensitivity. The NestJS scenario is repeated with `DB_POOL_SIZE = 1` (yielding exactly 4 total connections across the PM2 cluster, matching PHP-FPM). This control run is reported alongside the main results to assess whether performance differences stem from application concurrency or connection availability, without replacing the primary H2 verdict rules.

### S3: Relation Complexity (H3)

Scenario S3 examines whether relation traversal increases the signed difference between Laravel and NestJS relative to a single-table read. EP4 (nested relations) is the primary endpoint and EP1 is the baseline, measured inside S3 so that both come from the same scenario. EP5 (many-to-many) is a secondary observation. EP6 (JOINs with aggregation) is database-bound and is reported as an observation without entering the verdict; if resource saturation makes higher levels uninformative, it is measured only at 1 and 2 VU. Concurrency levels are 1, 2, 4 and 10 virtual users for EP1, EP4 and EP5. The verdict is evaluated at 2 VU, with 1 VU as the consistency level; 4 and 10 VU are observations (repetitions in Section 3.6).

**Verdict.** For endpoint k let S_k = p95_L(k) − p95_N(k), computed from the medians of the repetition-level p95 values. The primary statistic is D = S_EP4 − S_EP1, in milliseconds; a positive D means that Laravel falls further behind NestJS on the relation-heavy endpoint than on the baseline. H3 is **supported** when the lower bound of the 95% bootstrap CI of D at 2 VU exceeds the fixed practical threshold of 2 ms (twice the 1-ms resolution of p95) and the estimate of D at 1 VU is positive. Otherwise H3 is **not supported**. In both cases, D and its 95% CI are reported, allowing the reader to distinguish a near-zero, small, or reversed effect. A negative D cannot support H3. This signed contrast tests the directional claim that relation complexity increases Laravel's disadvantage; it is not equivalent to testing whether the absolute framework gap increases regardless of which framework is slower. If the validity rule of Section 3.3 fails at 2 VU, H3 is not evaluable.

**Reported beside the verdict.** The ratio of median p95 and the analogous contrasts computed from mean response time and from N/X are reported alongside D and its CI. The hypothesis concerns the combined effect of relation access, ORM hydration, SQL generation, database execution and serialization; it does not isolate ORM overhead or establish a mechanism.

**Statement counts.** One instrumented request per endpoint (header `X-Debug-Queries`, answered with `X-Query-Count`) records the application-level statement count; the diagnostic header is absent from benchmark traffic. The count is reported with the response size and does not include route-model binding or transaction-control statements.

### Endpoint complexity summary

The "Data-access complexity" column describes the logical relational depth of each endpoint. For relation-traversing read endpoints (EP2–EP5) this is realised through the unified query-based eager loading (separate `SELECT ... WHERE IN` statements) in both frameworks; only EP6 uses explicit SQL JOINs with aggregation. All read scenarios are executed using a JWT token with the Manager role, so that role-based query scopes (e.g. the order list at EP3, which is filtered to the authenticated waiter's own orders but unrestricted for managers) return a deterministic, identically sized result set across both frameworks.

| Endpoint | Method | Data-access complexity | Scenario |
|----------|--------|------------------------|----------|
| EP1: `/api/tables` | GET | baseline (no relations) | S1, S3 |
| EP2: `/api/menu-items` | GET | 1 relation (eager) | S1 |
| EP3: `/api/orders` | GET | 2 relations (eager) | S2 |
| EP4: `/api/orders/{id}` | GET | 3-level nested eager load | S3 |
| EP5: `/api/dishes/{id}/ingredients` | GET | N:M via pivot | S3 |
| EP6: `/api/dashboard/summary` | GET | 3 JOIN + aggregation | S3 |
| EP7: `/api/orders` | POST | transactional insert (order + items) | S2 |
| EP8: `/api/orders/{id}/status` | PATCH | simple UPDATE | S1 |
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

The allocation of host resources is structured to isolate the application under test. The framework containers operate within a strict 4-vCPU budget matched to four PHP-FPM workers and four PM2 instances, respectively. The remaining eight host cores absorb the execution overhead of the load generator and host operating system, preventing JMeter from competing for the application's CPU allocation. Because container CPU limits are enforced via cgroups quotas rather than pinned core affinity, residual host interference is mitigated by executing the benchmark as the sole active workload and evaluating medians across ten repetitions (Section 3.6).

Equalized, explicitly declared resource caps prevent uneven CPU and memory allocation from confounding framework performance [25]. The environment is orchestrated via Docker Compose, running a single framework stack per measurement profile so that Laravel and NestJS never compete for CPU resources. Both applications connect to the same PostgreSQL 16 instance using isolated databases with identical schemas and seeded datasets. Each stack utilizes a dedicated `nginx:1.25` reverse proxy container: forwarding FastCGI requests to `public/index.php` for Laravel, and proxying HTTP/1.1 traffic with persistent keepalive connections to the Node.js cluster for NestJS. Access logging is disabled on both Nginx proxies to eliminate asymmetric I/O overhead. PostgreSQL stores its data directory on a dedicated named Docker volume rather than a WSL2 host bind mount, preventing cross-filesystem I/O bottlenecks.

JMeter 5.6.3 runs in CLI mode in an uncapped container attached directly to the internal Compose bridge network. Requests address the proxy by service name (`laravel-nginx` or `nestjs-nginx` on port 80), bypassing host port forwarding and Docker Desktop network translation to eliminate external network latency and variance.

Database connection management reflects the architectural paradigms of the respective runtimes. A PHP-FPM worker handles requests synchronously, holding a single database connection. To eliminate the ~7.5 ms connection setup overhead (comprising TCP handshakes, SCRAM-SHA-256 authentication, and PostgreSQL process spawning) compared to a ~0.4 ms query execution time, persistent PDO connections (`PDO::ATTR_PERSISTENT`) are enabled for Laravel. Conversely, NestJS workers handle concurrent requests using a `pg` connection pool configured to `DB_POOL_SIZE = 10` per PM2 worker (up to 40 connections total). This capacity difference is an inherent characteristic of the two concurrency models; its specific impact on H2 scalability is evaluated via the `DB_POOL_SIZE = 1` control run (Section 3.3).

Process-level concurrency is strictly symmetric across environments. PHP-FPM is configured with static process management (`pm = static`, `pm.max_children = 4`), while NestJS is deployed via PM2 in cluster mode with four worker instances matching the 4-vCPU container limit. This ensures neither framework receives a single-process hardware advantage. Requests compete for the shared PHP-FPM listening socket on the Laravel stack, whereas the PM2 master process handles connection distribution across Node.js workers.

PostgreSQL configuration parameters are pinned explicitly in the Compose environment (`max_connections = 100`, `shared_buffers = 128MB`, `work_mem = 4MB`, `effective_cache_size = 4GB`). Because the 100-connection limit comfortably exceeds the maximum capacity of both NestJS (40) and PHP-FPM (4), database-side connection exhaustion is excluded as a driver of saturation in S2.

## 3.5. Metrics

The primary and secondary metrics collected across all experimental scenarios are summarized in the table below:

**Collected research metrics:**

| Metric | Description | Collection Method |
|--------|-------------|-------------------|
| **Response time** | Median ($p_{50}$), 95th percentile ($p_{95}$), and 99th percentile ($p_{99}$) computed via the nearest-rank method per endpoint. | JMeter results file (`.jtl`), automated summary script |
| **Throughput** | Successful requests per second (RPS) evaluated over the steady-state execution window. | JMeter results file (`.jtl`) |
| **Error rate** | Percentage of requests failing to return expected status codes (HTTP 200 for reads/EP8; HTTP 201 for EP7) or exceeding the 30-second timeout. HTTP 422 responses on EP7 are classified as errors. Serves as a secondary saturation indicator in S2. | JMeter results file (`.jtl`) |
| **CPU utilization** | Mean and peak CPU usage of the application container (as a fraction of its 4 assigned vCPUs). Mean CPU of Nginx, PostgreSQL, and JMeter containers recorded concurrently; PostgreSQL mean CPU enters the low-load validity rule (Section 3.3). | `docker stats` sampled at ~0.5 s intervals |
| **Memory usage** | Mean and peak RAM usage of the application container in MiB. | `docker stats` sampled at ~0.5 s intervals |
| **Mean response time (secondary)** | Little's law estimate computed as $R \approx N / X$ (concurrency $N$ divided by throughput $X$). Provides a continuous metric independent of JMeter's 1-ms time quantization; used as a consistency check for closed workloads. | Derived via automated summary script |
| **CPU time per request (secondary)** | Application CPU allocation (as a fraction of one core) divided by throughput $X$. Evaluates computational cost per request. | Derived from `docker stats` and throughput |
| **Relational contrasts $S_k / D$ (H3)** | Signed $p_{95}$ latency gap $S_k = p_{95,L}(k) - p_{95,N}(k)$ for EP1 and EP4, and relational contrast $D = S_{\text{EP4}} - S_{\text{EP1}}$ in milliseconds, with a 95% bootstrap CI. | Derived via automated summary script |
| **Response payload size (secondary)** | HTTP response body size in bytes. Reported alongside H3 to decouple relational processing cost from network serialization volume. | JMeter verification pass |
| **SQL query count** | Number of database queries executed per request (S3 only). | Diagnostic header pass (`X-Debug-Queries` $\rightarrow$ `X-Query-Count`); Laravel `DB::getQueryLog()` / NestJS TypeORM query logger |

Evaluating tail latency percentiles ($p_{95}$, $p_{99}$) rather than arithmetic mean response time isolates worst-case performance under load, which reflects user experience under concurrency and is frequently masked by central tendencies [21, 23, 25]. Because JMeter records request elapsed time in whole-millisecond increments—introducing coarse quantization when baseline latencies approach 1–2 ms—the two secondary continuous metrics ($N/X$ and CPU time per request) complement percentile measurements. 

These secondary metrics decouple execution cost from queuing delay: when response latency increases under load while CPU time per request remains flat, latency growth is driven by queueing ahead of available worker processes rather than increased computational complexity. Neither secondary metric directly determines hypothesis verdicts.

## 3.6. Experimental Procedure

Unless a scenario explicitly states otherwise, every scenario adheres strictly to the following execution protocol:

1. **Warm-up phase** — Each repetition is preceded by a 2-minute warm-up run at the target endpoint and concurrency level. Warm-up results are discarded to allow JIT compilation (Node.js V8 TurboFan) and PHP OPcache/JIT engines to reach steady-state optimization. Kuffel and Walter [10] observed that median latency in Node.js applications drops significantly during initial execution under load due to V8 TurboFan optimizations, necessitating this warm-up exclusion. Both applications execute with symmetric production optimizations: Laravel utilizes OPcache (JIT enabled), configuration caching (`config:cache`), and route caching (`route:cache`), while NestJS runs from a pre-compiled production build.
2. **Execution window** — Measurements are collected over a 3-minute steady-state window. The initial 10 seconds of each run—during which virtual users are spawned—are excluded from latency metrics, and resource traces (`docker stats`) are trimmed to synchronize with this active window.
3. **Repetitions and reporting** — Main-series experiments are executed for $n = 10$ independent repetitions per test configuration. Results are reported as the median and standard deviation across repetition-level samples, alongside the 95% bootstrap confidence intervals defined in Section 3.3.
4. **Isolation and correctness gates** — Before each scenario and repetition, an automated reset procedure (`scripts/db-reset.sh`) restores the database from the seeded PostgreSQL template and restarts the application and Nginx containers of the stack under test. For state-changing endpoints, the database is restored again immediately after the warm-up pass to ensure identical starting row counts and sequence states across measurement runs. 

   Following each run, automated correctness gates validate data integrity:
   - **Read and update paths (EP1–EP6, EP8):** Verifies that dictionary and transactional row counts remain unchanged (EP8 updates status fields in-place).
   - **Order creation path (EP7):** Each request performs a transactional insert of an order along with its single associated order item. An automated integrity check verifies that the net increase in the `orders` and `order_items` tables exactly matches the number of successful HTTP 201 responses recorded by JMeter, enforcing a strict 1:1 relationship.
   - **Little's law consistency diagnostic:** The difference between directly measured mean response time and the Little's-law estimate ($N/X$) is evaluated as a secondary execution check.

   Any discrepancy in database row increments or test parameters invalidates the run, triggering an immediate investigation and a complete re-execution of that repetition.
5. **Interleaving and automation** — The complete sequence (reset, warm-up, steady-state measurement, resource tracing, and integrity verification) is executed via an automated scenario runner. To prevent host thermal throttling or background system drift from confounding framework performance, repetitions run in an outer loop while framework execution order is randomized in the inner loop using a fixed pseudo-random seed. Only one framework stack operates at any given time. Raw JMeter `.jtl` samples, `docker stats` traces, row count metadata, and execution logs are persisted to ensure all reported metrics can be re-derived.
6. **Workload and error handling** — Load is applied as a closed workload using JMeter threads operating without think time, establishing concurrency ($N$) rather than request rate as the controlled variable. Each execution begins with a single authentication request (EP10) in a JMeter `setUp` thread group; the resulting JWT is shared across all virtual users for that run. A failure during login aborts the run immediately. HTTP keep-alive connections are maintained across requests within each virtual user thread. A request is classified as an error if it exceeds the 30-second timeout or fails to return expected status codes (HTTP 200 for reads/EP8; HTTP 201 for EP7, with HTTP 422 validation failures counted as errors).

A single-repetition pilot study ($n = 1$; 60 s warm-up, 60 s measurement) was conducted prior to the main series. The pilot confirmed near-linear throughput scaling at 1–4 virtual users and identified saturation onset near 10 users. Consequently, the pilot preregistered 2 VU as the primary verdict level for S3 (with 1 VU as a consistency check), designated 4 and 10 VU as observational levels, and established the operational rule restricting EP6 to 1 and 2 VU if database saturation occurs. Pilot data are excluded from main-series results.