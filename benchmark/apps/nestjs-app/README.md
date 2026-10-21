# Aplikacja Benchmarkowa NestJS 11 (Node.js 24 LTS)

Aplikacja backendowa REST API symulująca system zarządzania restauracją (POS / Restaurant Management System), przygotowana jako badany obiekt do empirycznego porównania wydajności z frameworkiem Laravel w ramach pracy badawczej.

Aplikacja została zaprojektowana w architekturze modułowej i warstwowej z zachowaniem ścisłej symetrii architektonicznej, bazodanowej i domenowej względem implementacji w Laravelu.

---

## Spis Treści
1. [Architektura Aplikacji i Symetria z Laravelem](#1-architektura-aplikacji-i-symetria-z-laravelem)
2. [Konfiguracja Środowiskowa i Optymalizacje Runtime](#2-konfiguracja-%C5%9Brodowiskowa-i-optymalizacje-runtime)
3. [Szczegółowy Opis Endpointów](#3-szczeg%C3%B3%C5%82owy-opis-endpoint%C3%B3w)
4. [Warstwy Aplikacji i Struktura Kodu](#4-warstwy-aplikacji-i-struktura-kodu)
5. [Uruchamianie i Diagnostyka](#5-uruchamianie-i-diagnostyka)

---

## 1. Architektura Aplikacji i Symetria z Laravelem

Aplikacja w NestJS implementuje pełną ścieżkę obsługi żądań HTTP REST API z odwzorowaniem mechanizmów Laravel:

- **Routing i Prefiks Globalny:** Wszystkie endpointy biznesowe rejestrowane są pod prefiksem `/api` (`app.setGlobalPrefix('api')`), co zapewnia zgodność ze ścieżkami `routes/api.php` w Laravelu (z wyłączeniem głównego healthchecka `/`).
- **Uwierzytelnianie bezstanowe in-memory (`JwtStrategy`):** Implementacja strategii `passport-jwt` weryfikuje podpis tokenu JWT (HS256) w pamięci na podstawie deklaracji (*claims*: `sub`, `role`) bez wykonywania zapytań SQL do bazy danych, co odpowiada implementacji `ClaimJwtGuard` w Laravelu.
- **Odpowiednik Route-Model Binding (`BindOrderGuard`, `BindDishGuard`):** W NestJS guardy uruchamiają się przed interceptorami. Dzięki temu pobranie encji po kluczu głównym następuje przed startem pomiaru zapytań SQL – dokładnie tak jak w Laravelu, gdzie middleware `SubstituteBindings` działa przed `count.queries`.
- **Walidacja DTO:** `ValidationPipe` zintegrowany z biblioteką `class-validator` (`whitelist: true`, `transform: true`), odpowiadający Form Requestom w Laravelu.
- **Warstwa ORM (TypeORM w trybie Active Record):**
  - Encje dziedziczą po `BaseEntity` i korzystają ze statycznych metod (`find`, `save`, `createQueryBuilder`).
  - **Zunifikowana strategia ładowania relacji:** Skonfigurowano `relationLoadStrategy: 'query'`, co zmusza TypeORM do wykonywania oddzielnych zapytań `SELECT ... WHERE IN (...)` dla relacji (tak jak robi to domyślnie Eloquent), zamiast generowania pojedynczych złączeń `JOIN` prowadzących do asymetrii iloczynu kartezjańskiego.
- **Format odpowiedzi:**
  - **Koperta stronicowania (`common/pagination.ts`):** Funkcja `paginate()` generuje strukturę odpowiedzi identyczną z `LengthAwarePaginator` w Laravelu (`data`, `current_page`, `last_page`, `total`, `per_page`, `links`).
  - **Konwersja nazewnictwa (`SnakeCaseInterceptor`):** Globalny interceptor przekształca właściwości encji z `camelCase` na `snake_case`, co zapewnia bajtową zgodność struktury JSON z Laravelem.
- **Obsługa BigInt (`common/pg-bigint.ts`):** 64-bitowe identyfikatory PostgreSQL (`int8`) są automatycznie mapowane na natywne liczby JavaScript (`parseInt`), co zapobiega serializowaniu identyfikatorów jako ciągów tekstowych.

---

## 2. Konfiguracja Środowiskowa i Optymalizacje Runtime

Aplikacja uruchamiana jest w kontenerze Docker opartym o oficjalny obraz `node:24-bookworm-slim` z narzuconymi limitami cgroups (4 vCPU, 2 GiB RAM):

- **Zarządca procesów PM2 (`ecosystem.config.js`):**
  - Uruchomienie w trybie klastra Node.js: `exec_mode: 'cluster'`, `instances: 4`.
  - Dokładnie 4 procesy robocze odpowiadają 4 rdzeniom vCPU (symetrycznie do 4 workerów PHP-FPM w Laravelu).
- **Kompilacja i Środowisko Produkcyjne (`Dockerfile`):**
  - Wielostopniowy build Docker (*multi-stage build*): etap budowania kompiluje TypeScript (`nest build`), a obraz końcowy instaluje wyłącznie zależności produkcyjne (`npm ci --omit=dev`).
  - Wyłączenie zmiennych deweloperskich (`NODE_ENV=production`).
- **Pula połączeń z bazą danych PostgreSQL:**
  - Standardowy rozmiar puli: `DB_POOL_SIZE = 10` na proces roboczy PM2 (co daje łącznie do 40 połączeń w pełnym klastrze).
  - Grupa kontrolna (scenariusz S2-pool1): dynamiczne nadpisanie zmienną `DB_POOL_SIZE = 1` (łącznie 4 połączenia w klastrze), co pozwala odseparować wpływ rozmiaru puli od wydajności pętli zdarzeń (*Event Loop*).

---

## 3. Szczegółowy Opis Endpointów

Wszystkie endpointy biznesowe wymagają autoryzacji nagłówkiem `Authorization: Bearer <token>` (z wyjątkiem `EP0`).

> ### 📌 Zakres Badania: Artykuł Naukowy vs Praca Magisterska
> - **Artykuł naukowy:** Skupia się na wąskim zestawie kluczowych operacji (S1: EP1, EP5; S2: EP3, EP7; S3: EP1, EP2; uzupełniająco: EP4, EP6; pre-test: EP0, `/api/ping`).
> - **Praca magisterska (pełne repozytorium):** Obejmuje **wszystkie 10 endpointów**, włączając relacje wiele-do-wielu (EP8) oraz transakcje z indeksem wykluczającym GiST (EP9).

### Tabela Podsumowująca Endpointy

| ID | Metoda i Ścieżka | Rola / Scenariusz | Zakres Badania | Złożoność Relacji / Danych | Kontroler i Serwis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EP0** | `POST /api/auth/login` | Setup (pre-test) | **Artykuł + Praca mgr** | Weryfikacja hasła, wydanie JWT HS256 | `AuthController` |
| **PING** | `GET /api/ping` | Diagnostyka bazowa | **Artykuł + Praca mgr** | 0 DB (wyłącznie weryfikacja JWT w pamięci) | `PingController` |
| **EP1** | `GET /api/tables` | S1 (werdykt), S3 (baza) | **Artykuł + Praca mgr** | 0 relacji (odczyt pojedynczej tabeli słownikowej) | `TablesController@index` |
| **EP2** | `GET /api/menu-items` | S3 (główny werdykt) | **Artykuł + Praca mgr** | 1 relacja eager load (szerokość kolekcji: 40 encji) | `MenuItemsController@index` |
| **EP3** | `GET /api/orders` | S2 (główny werdykt) | **Artykuł + Praca mgr** | 2 relacje eager load (`table`, `waiter`) | `OrdersController@index` |
| **EP4** | `GET /api/orders/:id` | S3 (obserwacja) | **Artykuł + Praca mgr** | 3 poziomy zagłębienia eager load (~10 encji) | `OrdersController@show` |
| **EP5** | `PATCH /api/orders/:id/status` | S1 (werdykt) | **Artykuł + Praca mgr** | Prosty in-place `UPDATE` pojedynczego rekordu | `OrdersController@updateStatus` |
| **EP6** | `GET /api/dashboard/summary` | S3 (obserwacja) | **Artykuł + Praca mgr** | 3 JOIN + `GROUP BY` + agregacje SQL (30 dni) | `DashboardController@summary` |
| **EP7** | `POST /api/orders` | S2 (obserwacja zapisu) | **Artykuł + Praca mgr** | Zapis transakcyjny (walidacja + 2 tabele) | `OrdersController@create` |
| **EP8** | `GET /api/dishes/:id/ingredients` | Analiza relacji N:M | **Wyłącznie Praca mgr** | Relacja N:M przez tabelę asocjacyjną (pivot) | `DishesController@ingredients` |
| **EP9** | `POST /api/reservations` | Indeks GiST / blokady | **Wyłącznie Praca mgr** | Zapis z walidacją kolizji terminów w bazie | `ReservationsController@create` |

---

### Szczegóły Techniczne Poszczególnych Endpointów

#### EP10: `POST /api/auth/login`
- **Przeznaczenie:** Pobranie tokenu JWT używanego w nagłówkach zapytań przez generator JMeter.
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
- **Działanie:** Weryfikuje hasło za pomocą `bcryptjs` w tabeli `users` i generuje token HS256 z identycznym czasem życia jak w Laravelu.

#### `/api/ping`: `GET /api/ping`
- **Przeznaczenie:** Izolacja czystego narzutu frameworka NestJS, obsługi routingu HTTP i walidacji podpisu JWT w pamięci bez udziału bazy danych.
- **Odpowiedź (HTTP 200):**
  ```json
  {
    "status": "ok"
  }
  ```

#### EP1: `GET /api/tables` (Scenariusz S1 & S3)
- **Przeznaczenie:** Odczyt bazowy prostej tabeli słownikowej.
- **Złożoność SQL:** 0 złączeń. Wywołanie `RestaurantTable.findAndCount()` z sortowaniem po `table_number ASC` i stronicowaniem (20 rekordów).
- **Odpowiedź (HTTP 200):** Obiekt stronicowania zawierający 20 rekordów stolików.

#### EP2: `GET /api/menu-items` (Scenariusz S3)
- **Przeznaczenie:** Badanie narzutu szerokości hydratacji relacji ORM na kolekcji rekordów.
- **Złożoność SQL:** 1 relacja (`MenuItem.findAndCount({ relations: { dish: true } })`) z warunkiem `is_available = true`. Dzięki `relationLoadStrategy: 'query'` TypeORM wykonuje zapytanie bazowe oraz zapytanie `SELECT ... FROM dishes WHERE id IN (...)`.
- **Wynik:** Hydratacja 20 obiektów `MenuItem` i 20 powiązanych encji `Dish` (łącznie 40 obiektów).

#### EP3: `GET /api/orders` (Scenariusz S2)
- **Przeznaczenie:** Test skalowalności odczytu pod wysokim obciążeniem (200, 500, 1 000 VU).
- **Złożoność SQL:** 2 relacje eager load (`table`, `waiter`) z sortowaniem malejącym po `ordered_at DESC`. Menedżer widzi wszystkie zamówienia, kelner wyłącznie własne (`WHERE user_id = :id`), zachowując logikę `Order::scopeForUser` z Laravela.

#### EP4: `GET /api/orders/:id` (Scenariusz S3)
- **Przeznaczenie:** Badanie narzutu głębokości relacji (hierarchia obiektów).
- **Działanie:** Rekord zamówienia pobierany jest wcześniej przez `BindOrderGuard`. Następnie serwis doładowuje hierarchię relacji: stolik, kelnera oraz pozycje zamówienia z przypisanymi daniami (`relations: { menuItem: { dish: true } }`), tworząc drzewo ~10 encji.

#### EP5: `GET /api/dishes/:id/ingredients` (Rezerwa)
- **Przeznaczenie:** Odczyt relacji wiele-do-wielu (N:M) przez tabelę pośredniczącą `dish_ingredients`.
- **Działanie:** Rekord dania pobiera `BindDishGuard`. Zapytanie pobiera powiązane składniki i konstruuje obiekt `pivot` (`dish_id`, `ingredient_id`, `quantity`, `created_at`, `updated_at`), odzwierciedlając format zwracany przez Eloquenta.

#### EP6: `GET /api/dashboard/summary` (Scenariusz S3)
- **Przeznaczenie:** Agregacja analityczna zdominowana przez przetwarzanie SQL w bazie danych.
- **Złożoność SQL:**
  - Pojedyncze zapytanie wygenerowane przez `createQueryBuilder`: 3 złączenia `innerJoin` (`orders`, `menu_items`, `dishes`).
  - Filtrowanie okna 30 dni od daty referencyjnej `BENCH_NOW` (33 469 zamówień).
  - Grupowanie `groupBy('dishes.category')`.
  - Agregacje: `COUNT(DISTINCT orders.id)`, `SUM(quantity)`, `SUM(revenue)`, `AVG(...)`.

#### EP7: `POST /api/orders` (Scenariusz S2)
- **Przeznaczenie:** Test wydajności i skalowalności zapisu transakcyjnego pod wysokim obciążeniem.
- **Ciało żądania (JSON):**
  ```json
  {
    "table_id": 1,
    "items": [
      { "menu_item_id": 5, "quantity": 2, "notes": "Bez cebuli" },
      { "menu_item_id": 12, "quantity": 1 }
    ]
  }
  ```
- **Przebieg w `OrdersService` (w ramach `dataSource.transaction`):**
  1. Walidacja istnienia stolika `RestaurantTable` (błąd 422 przy braku).
  2. Walidacja dostępności wybranych pozycji `MenuItem` (błąd 422 przy niedostępności).
  3. Zapis zamówienia `manager.save(order)`.
  4. Wsadowy zapis pozycji `manager.save(items)`.
  5. Aktualizacja łącznej kwoty zamówienia (`total_price`).
- **Odpowiedź (HTTP 201):** Utworzone zamówienie wraz z pozycjami.

#### EP8: `PATCH /api/orders/:id/status` (Scenariusz S1)
- **Przeznaczenie:** Prosta modyfikacja w miejscu (*in-place update*).
- **Ciało żądania (JSON):**
  ```json
  {
    "status": "paid"
  }
  ```
- **Działanie:** Bezpośrednia aktualizacja pola `status` na powiązanej encji (`await order.save()`).

#### EP9: `POST /api/reservations` (Rezerwa)
- **Przeznaczenie:** Tworzenie rezerwacji z walidacją nakładania się terminów przez bazodanowe ograniczenie wykluczające (`EXCLUDE USING gist`). Wykrycie konfliktu (kod SQLSTATE `23P01`) jest mapowane na błąd HTTP 409.

---

## 4. Warstwy Aplikacji i Struktura Kodu

```
src/
├── auth/
│   ├── jwt.strategy.ts         # Bezstanowa walidacja JWT w pamięci (in-memory)
│   ├── jwt-auth.guard.ts       # Strażnik autoryzacji HTTP
│   └── auth.controller.ts      # Endpoint logowania (EP10)
├── common/
│   ├── bind-entity.guard.ts    # Odpowiednik Route-Model Binding z Laravela
│   ├── pagination.ts           # Implementacja koperty stronicowania Laravel LengthAwarePaginator
│   ├── snake-case.interceptor.ts # Serializacja camelCase -> snake_case
│   ├── query-count.interceptor.ts# Obsługa nagłówka diagnostycznego X-Debug-Queries
│   └── pg-bigint.ts            # Parsowanie int8 jako liczby całkowite
├── entities/                   # Encje TypeORM (Order, RestaurantTable, Dish itp.)
├── tables/                     # Moduł, kontroler i serwis stolików (EP1)
├── menu-items/                 # Moduł pozycji menu (EP2)
├── orders/                     # Moduł zamówień (EP3, EP4, EP7, EP8)
├── dishes/                     # Moduł dań i składników (EP5)
├── dashboard/                  # Moduł analityczny dashboardu (EP6)
└── reservations/               # Moduł rezerwacji (EP9)
```

---

## 5. Uruchamianie i Diagnostyka

### Uruchomienie w środowisku Docker
Stos NestJS uruchamiany jest z poziomu katalogu głównego `benchmark/`:

```bash
# Uruchomienie bazy danych i stosu NestJS
docker compose --profile nestjs up -d --build

# Sprawdzenie dostępności endpointu głównego
curl -i http://localhost:8081/

# Sprawdzenie diagnostycznego endpointu ping
curl -i -H "Authorization: Bearer <TOKEN>" http://localhost:8081/api/ping
```

### Inspekcja zapytań SQL (Diagnostyka S3)
Wysłanie żądania z nagłówkiem `X-Debug-Queries: true` zwraca w nagłówku odpowiedzi `X-Query-Count` liczbę instrukcji SQL wykonanych przez dany endpoint:

```bash
curl -i -H "Authorization: Bearer <TOKEN>" \
     -H "X-Debug-Queries: true" \
     http://localhost:8081/api/tables
```
*(W nagłówkach odpowiedzi pojawi się `X-Query-Count: 1`).*

---

## 6. Specyfikacja OpenAPI (Swagger)

Pełna, sformalizowana specyfikacja interfejsu API w standardzie **OpenAPI 3.0.3** dla aplikacji NestJS znajduje się w pliku:
- [`openapi.yaml`](./openapi.yaml)

Zawiera ona szczegółowe schematy żądań (DTO), odpowiedzi (z uwzględnieniem `snake_case` i stronicowania), typów wyliczeniowych (Enum), nagłówków diagnostycznych oraz kodów błędów. Może być bezpośrednio zaimportowana do narzędzi takich jak Swagger UI, Postman, Insomnia czy Redoc.

