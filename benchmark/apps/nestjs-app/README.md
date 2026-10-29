# Aplikacja Benchmarkowa NestJS 11 (Node.js 24 LTS)

Aplikacja backendowa REST API symulująca system zarządzania restauracją (POS / Restaurant Management System), przygotowana jako badany obiekt do empirycznego porównania wydajności z frameworkiem Laravel w ramach pracy badawczej (artykułu naukowego oraz pracy magisterskiej).

Aplikacja została zaprojektowana w architekturze modułowej i warstwowej z zachowaniem ścisłej symetrii architektonicznej, bazodanowej i domenowej względem implementacji w Laravelu.

---

## Spis Treści
1. [Architektura Aplikacji i Symetria z Laravelem](#1-architektura-aplikacji-i-symetria-z-laravelem)
2. [Konfiguracja Środowiskowa i Optymalizacje Runtime](#2-konfiguracja-%C5%9Brodowiskowa-i-optymalizacje-runtime)
3. [Szczegółowy Opis Endpointów](#3-szczeg%C3%B3%C5%82owy-opis-endpoint%C3%B3w)
4. [Warstwy Aplikacji i Struktura Kodu](#4-warstwy-aplikacji-i-struktura-kodu)
5. [Uruchamianie i Diagnostyka](#5-uruchamianie-i-diagnostyka)
6. [Specyfikacja OpenAPI (Swagger)](#6-specyfikacja-openapi-swagger)

---

## 1. Architektura Aplikacji i Symetria z Laravelem

Aplikacja w NestJS implementuje pełną ścieżkę obsługi żądań HTTP REST API z odwzorowaniem mechanizmów Laravel:

- **Routing i Prefiks Globalny:** Wszystkie endpointy biznesowe rejestrowane są pod prefiksem `/api` (`app.setGlobalPrefix('api')`), co zapewnia zgodność ze ścieżkami `routes/api.php` w Laravelu (z wyłączeniem głównego healthchecka `/`).
- **Uwierzytelnianie bezstanowe in-memory (`JwtStrategy`):** Implementacja strategii `passport-jwt` weryfikuje podpis tokenu JWT (HS256) w pamięci na podstawie deklaracji (*claims*: `sub`, `role`) bez wykonywania zapytań SQL do bazy danych, co odpowiada implementacji `ClaimJwtGuard` w Laravelu.
- **Odpowiednik Route-Model Binding (`BindOrderGuard`, `BindDishGuard`):** W NestJS guardy uruchamiają się przed interceptorami. Dzięki temu pobranie encji po kluczu głównym następuje przed startem pomiaru zapytań SQL w `QueryCountInterceptor` – dokładnie tak jak w Laravelu, gdzie middleware `SubstituteBindings` działa przed `count.queries`.
- **Walidacja DTO:** `ValidationPipe` zintegrowany z biblioteką `class-validator` (`whitelist: true`, `transform: true`), odpowiadający klasom Form Request w Laravelu.
- **Warstwa ORM (TypeORM w trybie Active Record):**
  - Encje dziedziczą po `BaseEntity` i korzystają ze statycznych metod (`find`, `findAndCount`, `save`, `createQueryBuilder`).
  - **Zunifikowana strategia ładowania relacji:** Skonfigurowano `relationLoadStrategy: 'query'`, co wymusza na TypeORM wykonywanie oddzielnych zapytań `SELECT ... WHERE id IN (...)` dla relacji (tak jak robi to domyślnie Eloquent), zamiast generowania pojedynczych złączeń `JOIN` prowadzących do asymetrii rozmiaru przesyłanych krotek.
- **Format odpowiedzi:**
  - **Koperta stronicowania (`common/pagination.ts`):** Funkcja `paginate()` generuje strukturę odpowiedzi identyczną z `LengthAwarePaginator` w Laravelu (`data`, `current_page`, `last_page`, `total`, `per_page`, `links`).
  - **Konwersja nazewnictwa (`SnakeCaseInterceptor`):** Globalny interceptor przekształca właściwości encji z `camelCase` na `snake_case`, co zapewnia bajtową zgodność struktury JSON z Laravelem.
- **Obsługa BigInt (`common/pg-bigint.ts`):** 64-bitowe identyfikatory PostgreSQL (`int8`) są automatycznie mapowane na natywne liczby JavaScript (`parseInt`), co zapobiega serializowaniu identyfikatorów jako ciągów tekstowych.

---

## 2. Konfiguracja Środowiskowa i Optymalizacje Runtime

Aplikacja uruchamiana jest w kontenerze Docker opartym o oficjalny obraz `node:24-bookworm-slim` z narzuconymi limitami cgroups (4 vCPU, 2 GiB RAM):

- **Zarządca procesów PM2 (`ecosystem.config.js`):**
  - Uruchomienie w trybie klastra Node.js: `exec_mode: 'cluster'`, `instances: 4`.
  - Dokładnie 4 procesy robocze (4 niezależne pętle zdarzeń *Event Loop* V8) odpowiadają 4 rdzeniom vCPU (symetrycznie do 4 workerów PHP-FPM w Laravelu).
- **Kompilacja i Środowisko Produkcyjne (`Dockerfile`):**
  - Wielostopniowy build Docker (*multi-stage build*): etap budowania kompiluje TypeScript (`nest build`), a obraz końcowy instaluje wyłącznie zależności produkcyjne (`npm ci --omit=dev`).
  - Wyłączenie trybu deweloperskiego (`NODE_ENV=production`).
- **Pula połączeń z bazą danych PostgreSQL (`pg` Pool):**
  - **Konfiguracja domyślna (`DB_POOL_SIZE = 10`):** 10 połączeń na proces roboczy PM2, co daje łącznie do **40 równoległych połączeń** w całym klastrze.
  - **Seria kontrolna wrażliwości (`DB_POOL_SIZE = 1`, scenariusz `s2-pool1`):** dynamiczne ograniczenie puli do 1 połączenia na proces PM2 (łącznie **4 połączenia** w klastrze, identycznie jak w domyślnej konfiguracji 4 workerów PHP-FPM), co pozwala odseparować wpływ rozmiaru puli połączeń od narzutu środowiska wykonawczego Node.js.

---

## 3. Szczegółowy Opis Endpointów

Wszystkie endpointy biznesowe wymagają autoryzacji nagłówkiem `Authorization: Bearer <token>` (z wyjątkiem `EP0`).

> ### 📌 Zakres Badania: Artykuł Naukowy vs Praca Magisterska
> - **Artykuł naukowy (8 stron):** Obejmuje zestaw głównych operacji badawczych:
>   - **S1 (H1 – Baseline CRUD):** `EP1`, `EP5` (poziomy werdyktowe: 1 i 2 VU),
>   - **S2 (H2 – Scalability & Stress):** `EP3` (główny odczyt), `EP7` (zapis transakcyjny) oraz seria wrażliwości `DB_POOL_SIZE = 1` (`s2-pool1`) przy 200, 500 i 1000 VU,
>   - **S3 (H3 – Relational Complexity):** `EP2b` (punkt odniesienia *same-table baseline*), `EP2` (główny werdykt szerokości relacji), `EP4` (obserwacja głębokości 3-poziomowej) oraz `EP6` (obserwacja agregacji *database-bound*) przy 1 i 2 VU,
>   - **Operacje techniczne:** `EP0` (logowanie pre-test) oraz `/api/ping`.
> - **Praca magisterska (pełne repozytorium i [`results.md`](../../../results.md)):** Obejmuje dodatkowo pełne fazy nasycenia (4 i 10 VU w S1/S3), wyniki `DB_POOL_SIZE = 1` dla zapisu `EP7`, relację wiele-do-wielu N:M (`EP8`), rezerwacje z indeksem wykluczającym GiST (`EP9`) oraz wyniki kampanii pilotażowych.

### Tabela Podsumowująca Endpointy

| ID | Metoda i Ścieżka | Rola / Scenariusz | Zakres Badania | Złożoność Relacji / Danych | Kontroler i Metoda |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EP0** | `POST /api/auth/login` | Setup (pre-test) | **Artykuł + Praca mgr** | Weryfikacja hasła, wydanie JWT HS256 | `AuthController@login` |
| **PING** | `GET /api/ping` | Diagnostyka bazowa | **Artykuł + Praca mgr** | 0 DB (wyłącznie weryfikacja JWT w pamięci) | `PingController` |
| **EP1** | `GET /api/tables` | S1 (werdykt H1), S3 (ref.) | **Artykuł + Praca mgr** | 0 relacji (odczyt pojedynczej tabeli słownikowej, 20 wierszy) | `TablesController@index` |
| **EP2** | `GET /api/menu-items` | S3 (główny werdykt H3) | **Artykuł + Praca mgr** | 1 relacja eager load (`dish`, kolekcja: 20 + 20 = 40 encji) | `MenuItemsController@index` |
| **EP2b** | `GET /api/menu-items/plain` | S3 (baseline H3) | **Artykuł + Praca mgr** | 0 relacji na tej samej tabeli `menu_items` (kontrola dla EP2, 20 encji) | `MenuItemsController@indexPlain` |
| **EP3** | `GET /api/orders` | S2 (główny werdykt H2) | **Artykuł + Praca mgr** | 2 relacje eager load (`table`, `waiter`) + głęboka paginacja | `OrdersController@index` |
| **EP4** | `GET /api/orders/:id` | S3 (obserwacja głębokości) | **Artykuł + Praca mgr** | 3 poziomy zagłębienia eager load (~10 encji, 5 zapytań SQL) | `OrdersController@show` |
| **EP5** | `PATCH /api/orders/:id/status` | S1 (werdykt H1 – zapis) | **Artykuł + Praca mgr** | Prosty in-place `UPDATE` pojedynczego rekordu | `OrdersController@updateStatus` |
| **EP6** | `GET /api/dashboard/summary` | S3 (obserwacja DB-bound) | **Artykuł + Praca mgr** | 3 `INNER JOIN` + `GROUP BY` + agregacje SQL (okno 30 dni) | `DashboardController@summary` |
| **EP7** | `POST /api/orders` | S2 (zapis transakcyjny) | **Artykuł + Praca mgr** | Zapis transakcyjny ACID (walidacja + `orders` + `order_items`) | `OrdersController@create` |
| **EP8** | `GET /api/dishes/:id/ingredients` | Analiza relacji N:M | **Wyłącznie Praca mgr** | Relacja N:M przez tabelę asocjacyjną (`dish_ingredients`) | `DishesController@ingredients` |
| **EP9** | `POST /api/reservations` | Indeks GiST / blokady | **Wyłącznie Praca mgr** | Zapis z blokadą `FOR UPDATE` i walidacją kolizji `EXCLUDE USING gist` | `ReservationsController@create` |

---

### Szczegóły Techniczne Poszczególnych Endpointów

#### EP0: `POST /api/auth/login`
- **Przeznaczenie:** Pobranie tokenu JWT używanego w nagłówkach zapytań przez generator JMeter (w grupie `setUp Thread Group`).
- **Ciało żądania (JSON):**
  ```json
  {
    "email": "manager@example.com",
    "password": "password"
  }
  ```
- **Odpowiedź (HTTP 200):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600
  }
  ```
- **Działanie:** Weryfikuje hasło za pomocą `bcryptjs` w tabeli `users` i generuje token HS256 z identycznym czasem życia i strukturą deklaracji jak w Laravelu.

#### `/api/ping`: `GET /api/ping`
- **Przeznaczenie:** Izolacja czystego narzutu frameworka NestJS, obsługi routingu HTTP i walidacji podpisu JWT w pamięci bez udziału bazy danych (0 zapytań SQL).
- **Odpowiedź (HTTP 200):**
  ```json
  {
    "status": "ok"
  }
  ```

#### EP1: `GET /api/tables` (Scenariusz S1 & S3)
- **Przeznaczenie:** Odczyt bazowy prostej tabeli słownikowej (główny endpoint odczytowy hipotezy H1).
- **Złożoność SQL:** 0 relacji. Wywołanie `RestaurantTable.findAndCount()` z sortowaniem po `table_number ASC` i stronicowaniem (20 rekordów).
- **Odpowiedź (HTTP 200):** Obiekt stronicowania zawierający 20 rekordów stolików.

#### EP2: `GET /api/menu-items` (Scenariusz S3 – główny werdykt H3)
- **Przeznaczenie:** Badanie narzutu szerokości hydratacji relacji ORM na kolekcji rekordów.
- **Złożoność SQL:** 1 relacja (`MenuItem.findAndCount({ where: { isAvailable: true }, relations: { dish: true } })`). Dzięki `relationLoadStrategy: 'query'` TypeORM wykonuje 3 zapytania SQL: `COUNT(*)`, zapytanie bazowe `SELECT ... FROM menu_items` oraz zapytanie `SELECT ... FROM dishes WHERE id IN (...)`.
- **Wynik:** Hydratacja 20 obiektów `MenuItem` i 20 powiązanych encji `Dish` (łącznie 40 obiektów).

#### EP2b: `GET /api/menu-items/plain` (Scenariusz S3 – punkt odniesienia H3)
- **Przeznaczenie:** Punkt odniesienia (*same-table baseline*) dla estymatora Difference-in-Differences ($D_k = S_k - S_{\text{EP2b}}$) w scenariuszu S3. Eliminuje wpływ różnic w tabeli, filtrach `WHERE` i rozmiarze strony względem `EP2`.
- **Złożoność SQL:** 0 relacji (`MenuItem.findAndCount({ where: { isAvailable: true } })` – 2 zapytania SQL: `COUNT(*)` oraz `SELECT ... FROM menu_items WHERE is_available = true LIMIT 20 OFFSET ?`).
- **Wynik:** Hydratacja 20 obiektów `MenuItem` bez dołączania encji `Dish`.

#### EP3: `GET /api/orders` (Scenariusz S2 – główny werdykt H2)
- **Przeznaczenie:** Test skalowalności odczytu pod wysokim obciążeniem współbieżnym (200, 500, 1 000 VU).
- **Złożoność SQL:** 2 relacje eager load (`table`, `waiter`) z sortowaniem malejącym po `ordered_at DESC` i stronicowaniem (4 zapytania SQL na żądanie). Menedżer widzi wszystkie zamówienia, kelner wyłącznie własne (`WHERE user_id = :id`), zachowując logikę `Order::scopeForUser` z Laravela.

#### EP4: `GET /api/orders/:id` (Scenariusz S3 – obserwacja głębokości)
- **Przeznaczenie:** Badanie narzutu głębokości relacji (wielopoziomowa hierarchia obiektów).
- **Działanie:** Rekord zamówienia pobierany jest przez `BindOrderGuard`. Następnie serwis doładowuje hierarchię relacji: stolik, kelnera oraz pozycje zamówienia z przypisanymi pozycjami menu i daniami (`relations: { menuItem: { dish: true } }`), tworząc drzewo ~10 encji w 5 zapytaniach SQL.

#### EP5: `PATCH /api/orders/:id/status` (Scenariusz S1 – werdykt H1 dla zapisu)
- **Przeznaczenie:** Prosta modyfikacja w miejscu (*in-place update*).
- **Ciało żądania (JSON):**
  ```json
  {
    "status": "paid"
  }
  ```
- **Działanie:** Pobranie encji przez `BindOrderGuard` i aktualizacja pola `status` (`await order.save()`). W przypadku zmiany wartości `TypeORM.save()` wykonuje odczyt weryfikujący oraz `UPDATE ... RETURNING updated_at` opakowany w transakcję.

#### EP6: `GET /api/dashboard/summary` (Scenariusz S3 – obserwacja *database-bound*)
- **Przeznaczenie:** Agregacja analityczna zdominowana przez przetwarzanie SQL w bazie danych (~145 ms CPU w PostgreSQL).
- **Złożoność SQL:**
  - Pojedyncze zapytanie wygenerowane przez `createQueryBuilder`: 3 złączenia `innerJoin` (`orders`, `menu_items`, `dishes`).
  - Filtrowanie okna 30 dni od zamrożonej daty referencyjnej `BENCH_NOW` (dokładnie 33 469 zamówień).
  - Grupowanie `groupBy('dishes.category')` i sortowanie `orderBy('total_revenue', 'DESC')`.
  - Agregacje: `COUNT(DISTINCT orders.id)`, `SUM(quantity)`, `SUM(revenue)`, `AVG(...)`.

#### EP7: `POST /api/orders` (Scenariusz S2 – zapis transakcyjny)
- **Przeznaczenie:** Test wydajności i skalowalności zapisu transakcyjnego pod wysokim obciążeniem (200, 500, 1 000 VU).
- **Ciało żądania (JSON):**
  ```json
  {
    "table_id": 1,
    "items": [
      { "menu_item_id": 5, "quantity": 2, "notes": "Bez cebuli" }
    ]
  }
  ```
- **Przebieg w `OrdersService` (w ramach transakcji ACID `dataSource.transaction`, 7 instrukcji SQL):**
  1. Walidacja istnienia stolika `RestaurantTable` oraz dostępności wybranych pozycji `MenuItem` (błąd 422 przy naruszeniu).
  2. Zapis zamówienia `manager.save(order)` ze statusem `open`.
  3. Zapis pozycji zamówienia `manager.save(items)`.
  4. Aktualizacja łącznej kwoty zamówienia (`total_price`) i zwrócenie utworzonej struktury.
- **Odpowiedź (HTTP 201):** Utworzone zamówienie wraz z pozycjami.

#### EP8: `GET /api/dishes/:id/ingredients` (Praca magisterska – relacja N:M)
- **Przeznaczenie:** Odczyt relacji wiele-do-wielu (N:M) przez tabelę pośredniczącą `dish_ingredients` (przebadany w pilotażu S3 i profilowaniu SQL).
- **Działanie:** Rekord dania pobiera `BindDishGuard`. Zapytanie pobiera powiązane składniki i konstruuje obiekt `pivot` (`dish_id`, `ingredient_id`, `quantity`, `created_at`, `updated_at`), odzwierciedlając format zwracany przez Eloquenta (łącznie 2 zapytania SQL).

#### EP9: `POST /api/reservations` (Praca magisterska – indeks wykluczający GiST)
- **Przeznaczenie:** Tworzenie rezerwacji z blokadą pesymistyczną `SELECT ... FOR UPDATE`, sprawdzeniem nakładania się przedziałów czasowych (`tsrange && tsrange`) i bazodanowym ograniczeniem wykluczającym (`EXCLUDE USING gist`). Wykrycie konfliktu (kod SQLSTATE `23P01`) jest mapowane na błąd HTTP 409.

---

## 4. Warstwy Aplikacji i Struktura Kodu

```
src/
├── auth/
│   ├── jwt.strategy.ts           # Bezstanowa walidacja JWT w pamięci (in-memory)
│   ├── jwt-auth.guard.ts         # Strażnik autoryzacji HTTP
│   └── auth.controller.ts        # Endpoint logowania (EP0)
├── common/
│   ├── bind-entity.guard.ts      # Odpowiednik Route-Model Binding z Laravela (BindOrderGuard, BindDishGuard)
│   ├── pagination.ts             # Implementacja koperty stronicowania Laravel LengthAwarePaginator
│   ├── snake-case.interceptor.ts # Serializacja camelCase -> snake_case
│   ├── query-count.interceptor.ts# Obsługa nagłówka diagnostycznego X-Debug-Queries -> X-Query-Count
│   └── pg-bigint.ts              # Parsowanie int8 jako liczby całkowite JavaScript
├── entities/                     # Encje TypeORM (Order, OrderItem, RestaurantTable, Dish, MenuItem itp.)
├── tables/                       # Moduł, kontroler i serwis stolików (EP1)
├── menu-items/                   # Moduł pozycji menu (EP2 oraz EP2b /plain)
├── orders/                       # Moduł zamówień (EP3, EP4, EP5, EP7)
├── dishes/                       # Moduł dań i składników N:M (EP8)
├── dashboard/                    # Moduł analityczny dashboardu (EP6)
└── reservations/                 # Moduł rezerwacji z indeksem GiST (EP9)
```

---

## 5. Uruchamianie i Diagnostyka

### Uruchomienie w środowisku Docker
Stos NestJS uruchamiany jest z poziomu katalogu `benchmark/`:

```bash
# Uruchomienie bazy danych i stosu NestJS
docker compose --profile nestjs up -d --build

# Sprawdzenie dostępności endpointu głównego
curl -i http://localhost:8081/

# Sprawdzenie diagnostycznego endpointu ping
curl -i -H "Authorization: Bearer <TOKEN>" http://localhost:8081/api/ping
```

### Inspekcja zapytań SQL (Diagnostyka S3)
Wysłanie żądania z nagłówkiem `X-Debug-Queries: 1` zwraca w nagłówku odpowiedzi `X-Query-Count` liczbę instrukcji SQL zarejestrowanych w `QueryCountInterceptor`:

```bash
curl -i -H "Authorization: Bearer <TOKEN>" \
     -H "X-Debug-Queries: 1" \
     http://localhost:8081/api/menu-items
```
*(Pełne profilowanie wszystkich instrukcji SQL wraz z czasem wykonania po stronie serwera realizuje skrypt `scripts/sql-compare.sh nestjs` oparty o widok `pg_stat_statements`).*

---

## 6. Specyfikacja OpenAPI (Swagger)

Pełna, sformalizowana specyfikacja interfejsu API w standardzie **OpenAPI 3.0.3** dla aplikacji NestJS znajduje się w pliku:
- [`openapi.yaml`](./openapi.yaml)

Zawiera ona szczegółowe schematy żądań (DTO), odpowiedzi (z uwzględnieniem `snake_case` i stronicowania), typów wyliczeniowych (Enum), nagłówków diagnostycznych oraz kodów błędów. Może być bezpośrednio zaimportowana do narzędzi takich jak Swagger UI, Postman, Insomnia czy Redoc.
