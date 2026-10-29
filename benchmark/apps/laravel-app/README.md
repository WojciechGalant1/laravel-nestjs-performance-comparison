# Aplikacja Benchmarkowa Laravel 13 (PHP 8.4)

Aplikacja backendowa REST API symulująca system zarządzania restauracją (POS / Restaurant Management System), przygotowana jako badany obiekt do empirycznego porównania wydajności z frameworkiem NestJS w ramach pracy badawczej (artykułu naukowego oraz pracy magisterskiej).

Aplikacja została zaprojektowana w architekturze warstwowej MVC z zachowaniem ścisłej symetrii architektonicznej, bazodanowej i domenowej względem implementacji w NestJS.

---

## Spis Treści
1. [Architektura Aplikacji](#1-architektura-aplikacji)
2. [Konfiguracja Środowiskowa i Optymalizacje Runtime](#2-konfiguracja-%C5%9Brodowiskowa-i-optymalizacje-runtime)
3. [Szczegółowy Opis Endpointów](#3-szczeg%C3%B3%C5%82owy-opis-endpoint%C3%B3w)
4. [Warstwy Aplikacji i Struktura Kodu](#4-warstwy-aplikacji-i-struktura-kodu)
5. [Uruchamianie i Diagnostyka](#5-uruchamianie-i-diagnostyka)
6. [Specyfikacja OpenAPI (Swagger)](#6-specyfikacja-openapi-swagger)

---

## 1. Architektura Aplikacji

Aplikacja implementuje pełną ścieżkę obsługi żądań HTTP REST API:
- **Routing:** Zdefiniowany w `routes/api.php` z obsługą prefiksów i powiązań parametrów (*Route Model Binding* przez middleware `SubstituteBindings`).
- **Uwierzytelnianie bezstanowe in-memory (`ClaimJwtGuard`):** Uwierzytelnianie tokenem JWT (HS256) realizowane w pamięci na podstawie deklaracji (*claims*: `sub`, `role`) bez konieczności odpytywania bazy danych PostgreSQL o użytkownika przy każdym żądaniu.
- **Warstwa Walidacji:** Dedykowane klasy Form Request (`StoreOrderRequest`, `UpdateOrderStatusRequest`, `StoreReservationRequest`).
- **Warstwa Usług (Services):** Hermetyzacja logiki biznesowej (`OrderService`, `DashboardService`, `ReservationService`).
- **Warstwa ORM (Eloquent):** Active Record z jawną strategią eager loading (osobne zapytania `SELECT ... WHERE id IN (...)`), odpowiadającą konfiguracji `relationLoadStrategy: 'query'` w NestJS/TypeORM.
- **Format odpowiedzi:** Wszystkie kolekcje stronicowane zwracane są w standardowej kopercie stronicowania Laravel (`LengthAwarePaginator`: `data`, `current_page`, `last_page`, `total`, `per_page`, `links`), a klucze serializowane są w formacie `snake_case`.

---

## 2. Konfiguracja Środowiskowa i Optymalizacje Runtime

Aplikacja działa w kontenerze Docker opartym o obraz `php:8.4-fpm-bookworm` z narzuconymi limitami cgroups (4 vCPU, 2 GiB RAM):

- **PHP-FPM (`docker/php-fpm.conf`):**
  - Tryb statyczny: `pm = static`, `pm.max_children = ${PM_MAX_CHILDREN:-4}` (domyślnie dokładnie 1 proces roboczy na przydzielone vCPU, symetrycznie do 4 instancji PM2 w NestJS; w badaniach wrażliwości S2 dynamicznie skalowany w zakresie `PM_MAX_CHILDREN` $\in \{4, 8, 16, 24, 32, 40\}$).
  - Brak recyklingu procesów w trakcie pomiaru (`pm.max_requests = 0`).
  - Wyłączone logowanie dostępu (`access.log = /dev/null`) eliminuje asymetrię operacji dyskowych I/O.
- **OPcache i JIT (`docker/opcache.ini`):**
  - Włączony OPcache z pamięcią 256 MB (`opcache.memory_consumption = 256`).
  - Wyłączona walidacja znaczników czasu plików (`opcache.validate_timestamps = 0`) – kod źródłowy w obrazie kontenera jest niezmienny.
  - Włączony kompilator JIT w trybie `tracing` z buforem 128 MB (`opcache.jit = tracing`, `opcache.jit_buffer_size = 128M`).
- **Optymalizacje kontenera (`Dockerfile` i `docker/entrypoint.sh`):**
  - Autoloader zoptymalizowany pod produkcję na etapie budowania obrazu: `composer dump-autoload --classmap-authoritative --no-dev`.
  - Pamięć podręczna konfiguracji i routingu generowana przy starcie kontenera: `php artisan config:cache` oraz `php artisan route:cache`.
- **Baza Danych i Połączenia:**
  - PostgreSQL 16.
  - Stałe połączenia PDO (`PDO::ATTR_PERSISTENT => true`), co daje 1 trwałe połączenie na proces roboczy PHP-FPM (domyślnie 4 stałe połączenia do bazy danych, utrzymywane pomiędzy kolejnymi żądaniami HTTP bez narzutu TCP/auth handshake).

---

## 3. Szczegółowy Opis Endpointów

Wszystkie endpointy biznesowe wymagają autoryzacji nagłówkiem `Authorization: Bearer <token>` (z wyjątkiem `EP0`).

> ### 📌 Zakres Badania: Artykuł Naukowy vs Praca Magisterska
> - **Artykuł naukowy (8 stron):** Obejmuje zestaw głównych operacji badawczych:
>   - **S1 (H1 – Baseline CRUD):** `EP1`, `EP5` (poziomy werdyktowe: 1 i 2 VU),
>   - **S2 (H2 – Scalability & Stress):** `EP3` (główny odczyt), `EP7` (zapis transakcyjny) oraz seria wrażliwości `PM_MAX_CHILDREN = 8` i `40` przy 200, 500 i 1000 VU,
>   - **S3 (H3 – Relational Complexity):** `EP2b` (punkt odniesienia *same-table baseline*), `EP2` (główny werdykt szerokości relacji), `EP4` (obserwacja głębokości 3-poziomowej) oraz `EP6` (obserwacja agregacji *database-bound*) przy 1 i 2 VU,
>   - **Operacje techniczne:** `EP0` (logowanie pre-test) oraz `/api/ping`.
> - **Praca magisterska (pełne repozytorium i [`results.md`](../../../results.md)):** Obejmuje dodatkowo pełne fazy nasycenia (4 i 10 VU w S1/S3), pełną siatkę `pm.max_children` $\in \{4..40\}$, relację wiele-do-wielu N:M (`EP8`), rezerwacje z indeksem wykluczającym GiST (`EP9`) oraz wyniki kampanii pilotażowych.

### Tabela Podsumowująca Endpointy

| ID | Metoda i Ścieżka | Rola / Scenariusz | Zakres Badania | Złożoność Relacji / Danych | Kontroler i Akcja |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EP0** | `POST /api/auth/login` | Setup (pre-test) | **Artykuł + Praca mgr** | Uwierzytelnienie, wydanie JWT HS256 | `AuthController@login` |
| **PING** | `GET /api/ping` | Diagnostyka bazowa | **Artykuł + Praca mgr** | 0 DB (wyłącznie weryfikacja JWT w pamięci) | `PingController` |
| **EP1** | `GET /api/tables` | S1 (werdykt H1), S3 (ref.) | **Artykuł + Praca mgr** | 0 relacji (odczyt pojedynczej tabeli słownikowej, 20 wierszy) | `TableController@index` |
| **EP2** | `GET /api/menu-items` | S3 (główny werdykt H3) | **Artykuł + Praca mgr** | 1 relacja eager load (`dish`, kolekcja: 20 + 20 = 40 encji) | `MenuItemController@index` |
| **EP2b** | `GET /api/menu-items/plain` | S3 (baseline H3) | **Artykuł + Praca mgr** | 0 relacji na tej samej tabeli `menu_items` (kontrola dla EP2, 20 encji) | `MenuItemController@indexPlain` |
| **EP3** | `GET /api/orders` | S2 (główny werdykt H2) | **Artykuł + Praca mgr** | 2 relacje eager load (`table`, `waiter`) + głęboka paginacja | `OrderController@index` |
| **EP4** | `GET /api/orders/{order}` | S3 (obserwacja głębokości) | **Artykuł + Praca mgr** | 3 poziomy zagłębienia eager load (~10 encji, 5 zapytań SQL) | `OrderController@show` |
| **EP5** | `PATCH /api/orders/{order}/status` | S1 (werdykt H1 – zapis) | **Artykuł + Praca mgr** | Prosty in-place `UPDATE` pojedynczego rekordu | `OrderController@updateStatus` |
| **EP6** | `GET /api/dashboard/summary` | S3 (obserwacja DB-bound) | **Artykuł + Praca mgr** | 3 `INNER JOIN` + `GROUP BY` + agregacje SQL (okno 30 dni) | `DashboardController@summary` |
| **EP7** | `POST /api/orders` | S2 (zapis transakcyjny) | **Artykuł + Praca mgr** | Zapis transakcyjny ACID (walidacja + `orders` + `order_items`) | `OrderController@store` |
| **EP8** | `GET /api/dishes/{dish}/ingredients` | Analiza relacji N:M | **Wyłącznie Praca mgr** | Relacja N:M przez tabelę asocjacyjną (`dish_ingredients`) | `DishController@ingredients` |
| **EP9** | `POST /api/reservations` | Indeks GiST / blokady | **Wyłącznie Praca mgr** | Zapis z blokadą `FOR UPDATE` i walidacją kolizji `EXCLUDE USING gist` | `ReservationController@store` |

---

### Szczegóły Techniczne Poszczególnych Endpointów

#### EP0: `POST /api/auth/login`
- **Przeznaczenie:** Pozyskanie tokenu uwierzytelniającego JWT używanego przez wątki testowe JMeter (w grupie `setUp Thread Group` przed pomiarem).
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
- **Działanie:** Weryfikuje dane uwierzytelniające w tabeli `users` i generuje token JWT HS256 zawierający `sub`, `role`, `iat`, `exp`.

#### `/api/ping`: `GET /api/ping`
- **Przeznaczenie:** Diagnostyka frameworka – izolacja czystego narzutu HTTP, routingu i weryfikacji podpisu JWT w pamięci bez udziału bazy danych (0 zapytań SQL).
- **Odpowiedź (HTTP 200):**
  ```json
  {
    "status": "ok"
  }
  ```

#### EP1: `GET /api/tables` (Scenariusz S1 & S3)
- **Przeznaczenie:** Pomiar bazowy czystego odczytu prostej tabeli słownikowej (główny endpoint odczytowy hipotezy H1).
- **Złożoność SQL:** 0 relacji (`Table::query()->orderBy('table_number')->paginate(20)` – zapytanie `COUNT(*)` oraz `SELECT ... FROM tables ORDER BY table_number ASC LIMIT 20 OFFSET ?`).
- **Odpowiedź (HTTP 200):** Obiekt stronicowania zawierający 20 rekordów stolików.

#### EP2: `GET /api/menu-items` (Scenariusz S3 – główny werdykt H3)
- **Przeznaczenie:** Badanie narzutu szerokości hydratacji obiektów ORM na kolekcji rekordów.
- **Złożoność SQL:** 1 relacja (`MenuItem::with('dish')->where('is_available', true)->paginate(20)`). Eloquent wykonuje 3 zapytania SQL: `COUNT(*)`, zapytanie bazowe `SELECT * FROM menu_items` oraz zapytanie eager loading `SELECT * FROM dishes WHERE id IN (...)`.
- **Wynik:** Hydratacja 20 obiektów `MenuItem` oraz 20 powiązanych encji `Dish` (łącznie 40 obiektów domenowych w pamięci).

#### EP2b: `GET /api/menu-items/plain` (Scenariusz S3 – punkt odniesienia H3)
- **Przeznaczenie:** Punkt odniesienia (*same-table baseline*) dla estymatora Difference-in-Differences ($D_k = S_k - S_{\text{EP2b}}$) w scenariuszu S3. Eliminuje wpływ różnic w strukturze tabeli, filtrach `WHERE` i rozmiarze strony względem `EP2`.
- **Złożoność SQL:** 0 relacji (`MenuItem::query()->where('is_available', true)->paginate(20)` – 2 zapytania SQL: `COUNT(*)` oraz `SELECT * FROM menu_items WHERE is_available = true LIMIT 20 OFFSET ?`).
- **Wynik:** Hydratacja 20 obiektów `MenuItem` bez dołączania relacji `dish`.

#### EP3: `GET /api/orders` (Scenariusz S2 – główny werdykt H2)
- **Przeznaczenie:** Test skalowalności odczytu pod wysokim obciążeniem współbieżnym (200, 500, 1 000 VU).
- **Złożoność SQL:** 2 relacje eager load (`table`, `waiter`) z sortowaniem malejącym po dacie `ordered_at` i stronicowaniem (20 zamówień na stronę, 4 zapytania SQL na żądanie).

#### EP4: `GET /api/orders/{order}` (Scenariusz S3 – obserwacja głębokości)
- **Przeznaczenie:** Badanie narzutu głębokości relacji (wielopoziomowa hierarchia obiektów).
- **Złożoność SQL:** 3-poziomowy nested eager loading (5 zapytań SQL łącznie z *Route Model Binding*):
  `$order->load(['table', 'waiter', 'orderItems.menuItem.dish'])`.
- **Wynik:** Pobranie pojedynczego zamówienia wraz ze stolikiem, kelnerem, listą pozycji zamówienia, powiązanymi pozycjami menu i daniami (~10 encji w grafie relacji).

#### EP5: `PATCH /api/orders/{order}/status` (Scenariusz S1 – werdykt H1 dla zapisu)
- **Przeznaczenie:** Prosta operacja zapisu/modyfikacji w miejscu (*in-place update*).
- **Ciało żądania (JSON):**
  ```json
  {
    "status": "paid"
  }
  ```
- **Działanie:** Pobranie rekordu przez *Route Model Binding* i aktualizacja statusu zamówienia w bazie (`UPDATE orders SET status = ?, updated_at = ? WHERE id = ?`). W przypadku gdy nowy status jest identyczny z bieżącym, mechanizm *dirty checking* w Eloquent ORM pomija instrukcję `UPDATE`.

#### EP6: `GET /api/dashboard/summary` (Scenariusz S3 – obserwacja *database-bound*)
- **Przeznaczenie:** Złożone zapytanie analityczne, w którym wąskim gardłem jest silnik relacyjny SQL (~138 ms CPU w PostgreSQL), a nie serializacja ORM.
- **Złożoność SQL:**
  - Pojedyncze zapytanie z 3 złączeniami `INNER JOIN`: `order_items` $\rightarrow$ `orders`, `order_items` $\rightarrow$ `menu_items`, `menu_items` $\rightarrow$ `dishes`.
  - Filtrowanie okna czasowego ostatnich 30 dni względem zamrożonej daty `BENCH_NOW` (dokładnie 33 469 zamówień).
  - Grupowanie `GROUP BY dishes.category` i sortowanie `ORDER BY total_revenue DESC`.
  - Funkcje agregujące: `COUNT(DISTINCT orders.id)`, `SUM(quantity)`, `SUM(quantity * unit_price)`, `AVG(unit_price)`.

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
- **Przebieg w `OrderService` (w ramach transakcji ACID `DB::transaction`, 7 instrukcji SQL):**
  1. Walidacja istnienia stolika `tables` oraz dostępności wybranych pozycji `menu_items` (`is_available = true`).
  2. `INSERT` do tabeli `orders` ze statusem `open`.
  3. Utworzenie rekordów `order_items` z cenami jednostkowymi pobranymi z bazy.
  4. Obliczenie sumy łącznej (`total_price`), `UPDATE` rekordu zamówienia i doładowanie relacji odpowiedzi.
- **Odpowiedź (HTTP 201):** Nowo utworzone zamówienie wraz z pozycjami.

#### EP8: `GET /api/dishes/{dish}/ingredients` (Praca magisterska – relacja N:M)
- **Przeznaczenie:** Odczyt relacji wiele-do-wielu (N:M) przez tabelę pośredniczącą `dish_ingredients` (przebadany w pilotażu S3 i profilowaniu SQL).
- **Złożoność SQL:** 2 zapytania SQL (odczyt dania `dishes` przez *Route Model Binding* + `SELECT ingredients ... INNER JOIN dish_ingredients` z dołączeniem atrybutów pivota `quantity`).

#### EP9: `POST /api/reservations` (Praca magisterska – indeks wykluczający GiST)
- **Przeznaczenie:** Tworzenie rezerwacji stolika z pesymistyczną blokadą `SELECT ... FOR UPDATE` oraz walidacją nakładania się przedziałów czasowych (`tsrange && tsrange`) i ograniczeniem `EXCLUDE USING gist` na poziomie silnika PostgreSQL.

---

## 4. Warstwy Aplikacji i Struktura Kodu

```
app/
├── Auth/
│   └── ClaimJwtGuard.php         # Niestandardowy guard JWT - bezstanowa rezolucja usera in-memory
├── Enums/                        # Typowane enumy (OrderStatus, TableStatus, UserRole itp.)
├── Exceptions/
│   └── BusinessRuleException.php # Wyjątki biznesowe mapowane na kody HTTP 422 / 409
├── Http/
│   ├── Controllers/              # Kontrolery MVC (OrderController, MenuItemController, TableController itp.)
│   ├── Middleware/
│   │   └── CountQueries.php      # Diagnostyka liczby zapytań SQL (nagłówek X-Debug-Queries -> X-Query-Count)
│   └── Requests/                 # Walidatory FormRequest (StoreOrderRequest, UpdateOrderStatusRequest itp.)
├── Models/                       # Modele Eloquent (Order, OrderItem, Table, Dish, MenuItem, Ingredient, Reservation)
├── Policies/
│   └── OrderPolicy.php           # Logika uprawnień (np. Waiter widzi tylko własne zamówienia)
└── Services/                     # Logika biznesowa (OrderService, DashboardService, ReservationService)
```

---

## 5. Uruchamianie i Diagnostyka

### Uruchomienie w środowisku Docker
Stos Laravel uruchamiany jest z poziomu katalogu `benchmark/`:

```bash
# Uruchomienie bazy danych i stosu Laravel
docker compose --profile laravel up -d --build

# Sprawdzenie dostępności endpointu healthcheck
curl -i http://localhost:8080/up
```

### Inspekcja zapytań SQL (Diagnostyka S3)
Wysłanie żądania z nagłówkiem `X-Debug-Queries: 1` zwraca w nagłówku odpowiedzi `X-Query-Count` liczbę instrukcji SQL zarejestrowanych po etapie *Route Model Binding*:

```bash
curl -i -H "Authorization: Bearer <TOKEN>" \
     -H "X-Debug-Queries: 1" \
     http://localhost:8080/api/menu-items
```
*(Pełne profilowanie wszystkich instrukcji SQL wraz z czasem wykonania po stronie serwera realizuje skrypt `scripts/sql-compare.sh laravel` oparty o widok `pg_stat_statements`).*

---

## 6. Specyfikacja OpenAPI (Swagger)

Pełna, sformalizowana specyfikacja interfejsu API w standardzie **OpenAPI 3.0.3** znajduje się w pliku:
- [`openapi.yaml`](./openapi.yaml)

Zawiera ona szczegółowe schematy żądań, odpowiedzi, typów wyliczeniowych (Enum), nagłówków diagnostycznych oraz struktury kopert paginacji. Może być bezpośrednio importowana do narzędzi takich jak Swagger UI, Postman, Insomnia czy Redoc.
