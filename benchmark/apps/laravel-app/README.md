# Aplikacja Benchmarkowa Laravel 13 (PHP 8.4)

Aplikacja backendowa REST API symulująca system zarządzania restauracją (POS / Restaurant Management System), przygotowana jako badany obiekt do empirycznego porównania wydajności z frameworkiem NestJS w ramach pracy badawczej.

Aplikacja została zaprojektowana w architekturze warstwowej MVC z zachowaniem ścisłej symetrii architektonicznej i domenowej względem implementacji w NestJS.

---

## Spis Treści
1. [Architektura Aplikacji](#1-architektura-aplikacji)
2. [Konfiguracja Środowiskowa i Optymalizacje Runtime](#2-konfiguracja-%C5%9Brodowiskowa-i-optymalizacje-runtime)
3. [Szczegółowy Opis Endpointów](#3-szczeg%C3%B3%C5%82owy-opis-endpoint%C3%B3w)
4. [Warstwy Aplikacji i Struktura Kodu](#4-warstwy-aplikacji-i-struktura-kodu)
5. [Uruchamianie i Diagnostyka](#5-uruchamianie-i-diagnostyka)

---

## 1. Architektura Aplikacji

Aplikacja implementuje pełną ścieżkę obsługi żądań HTTP REST API:
- **Routing:** Zdefiniowany w `routes/api.php` z obsługą prefiksów i powiązań parametrów (Route Model Binding).
- **Uwierzytelnianie bezstanowe in-memory (`ClaimJwtGuard`):** Uwierzytelnianie tokenem JWT (HS256) realizowane w pamięci na podstawie deklaracji (*claims*: `sub`, `role`) bez konieczności odpytywania bazy danych PostgreSQL o użytkownika przy każdym żądaniu.
- **Warstwa Walidacji:** Dedykowane klasy Form Request (`StoreOrderRequest`, `UpdateOrderStatusRequest`, `StoreReservationRequest`).
- **Warstwa Usług (Services):** Hermetyzacja logiki biznesowej (`OrderService`, `DashboardService`, `ReservationService`).
- **Warstwa ORM (Eloquent):** Active Record z jawną strategią eager loading (osobne zapytania `SELECT IN (...)`), odpowiadającą konfiguracji `relationLoadStrategy: 'query'` w NestJS/TypeORM.
- **Format odpowiedzi:** Wszystkie kolekcje zwracane są w standardowej kopercie stronicowania Laravel (`data`, `current_page`, `last_page`, `total`, `per_page`), a klucze serializowane są w formacie `snake_case`.

---

## 2. Konfiguracja Środowiskowa i Optymalizacje Runtime

Aplikacja działa w kontenerze Docker opartym o obraz `php:8.4-fpm-bookworm` z narzuconymi limitami cgroups (4 vCPU, 2 GiB RAM):

- **PHP-FPM (`docker/php-fpm.conf`):**
  - Tryb statyczny: `pm = static`, `pm.max_children = 4` (dokładnie 1 proces roboczy na przydzielone vCPU, symetrycznie do 4 instancji PM2 w NestJS).
  - Wyłączone logowanie dostępu (`access.log = /dev/null`) eliminuje asymetrię operacji dyskowych I/O.
- **OPcache i JIT (`docker/opcache.ini`):**
  - Włączony OPcache z pamięcią 256 MB.
  - Wyłączona walidacja znaczników czasu plików (`opcache.validate_timestamps = 0`) – pliki kodu w obrazie są niezmienne.
  - Włączony kompilator JIT w trybie `tracing` z buforem 128 MB (`opcache.jit_buffer_size = 128M`).
- **Optymalizacje kontenera (`docker/entrypoint.sh`):**
  - Autoloader zoptymalizowany pod produkcję: `composer dump-autoload --classmap-authoritative`.
  - Pamięć podręczna konfiguracji i routingu generowana przy starcie kontenera: `php artisan config:cache` oraz `php artisan route:cache`.
- **Baza Danych i Połączenia:**
  - PostgreSQL 16.
  - Stałe połączenia PDO (`PDO::ATTR_PERSISTENT = true`), co daje 1 trwałe połączenie na proces roboczy PHP-FPM (łącznie 4 stałe połączenia do bazy danych).

---

## 3. Szczegółowy Opis Endpointów

Wszystkie endpointy biznesowe wymagają autoryzacji nagłówkiem `Authorization: Bearer <token>` (z wyjątkiem `EP0`).

> ### 📌 Zakres Badania: Artykuł Naukowy vs Praca Magisterska
> - **Artykuł naukowy:** Skupia się na wąskim zestawie kluczowych operacji (S1: EP1, EP5; S2: EP3, EP7; S3: EP1, EP2; uzupełniająco: EP4, EP6; pre-test: EP0, `/api/ping`).
> - **Praca magisterska (pełne repozytorium):** Obejmuje **wszystkie 10 endpointów**, włączając relacje wiele-do-wielu (EP8) oraz transakcje z indeksem wykluczającym GiST (EP9).

### Tabela Podsumowująca Endpointy

| ID | Metoda i Ścieżka | Rola / Scenariusz | Zakres Badania | Złożoność Relacji / Danych | Kontroler i Akcja |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EP0** | `POST /api/auth/login` | Setup (pre-test) | **Artykuł + Praca mgr** | Uwierzytelnienie, wydanie JWT HS256 | `AuthController@login` |
| **PING** | `GET /api/ping` | Diagnostyka bazowa | **Artykuł + Praca mgr** | 0 DB (wyłącznie weryfikacja JWT w pamięci) | `PingController` |
| **EP1** | `GET /api/tables` | S1 (werdykt), S3 (baza) | **Artykuł + Praca mgr** | 0 relacji (odczyt pojedynczej tabeli słownikowej) | `TableController@index` |
| **EP2** | `GET /api/menu-items` | S3 (główny werdykt) | **Artykuł + Praca mgr** | 1 relacja eager load (szerokość kolekcji: 40 encji) | `MenuItemController@index` |
| **EP3** | `GET /api/orders` | S2 (główny werdykt) | **Artykuł + Praca mgr** | 2 relacje eager load (`table`, `waiter`) | `OrderController@index` |
| **EP4** | `GET /api/orders/{id}` | S3 (obserwacja) | **Artykuł + Praca mgr** | 3 poziomy zagłębienia eager load (~10 encji) | `OrderController@show` |
| **EP5** | `PATCH /api/orders/{id}/status` | S1 (werdykt) | **Artykuł + Praca mgr** | Prosty in-place `UPDATE` pojedynczego rekordu | `OrderController@updateStatus` |
| **EP6** | `GET /api/dashboard/summary` | S3 (obserwacja) | **Artykuł + Praca mgr** | 3 JOIN + `GROUP BY` + agregacje SQL (30 dni) | `DashboardController@summary` |
| **EP7** | `POST /api/orders` | S2 (obserwacja zapisu) | **Artykuł + Praca mgr** | Zapis transakcyjny (walidacja + 2 tabele) | `OrderController@store` |
| **EP8** | `GET /api/dishes/{dish}/ingredients` | Analiza relacji N:M | **Wyłącznie Praca mgr** | Relacja N:M przez tabelę asocjacyjną (pivot) | `DishController@ingredients` |
| **EP9** | `POST /api/reservations` | Indeks GiST / blokady | **Wyłącznie Praca mgr** | Zapis z walidacją kolizji terminów w bazie | `ReservationController@store` |

---

### Szczegóły Techniczne Poszczególnych Endpointów

#### EP10: `POST /api/auth/login`
- **Przeznaczenie:** Pozyskanie tokenu uwierzytelniającego JWT używanego przez wątki testowe JMeter.
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
- **Działanie:** Weryfikuje dane uwierzytelniające w tabeli `users` (`auth()->attempt()`) i generuje 164-znakowy token JWT HS256 zawierający `sub`, `role`, `iat`, `exp`.

#### `/api/ping`: `GET /api/ping`
- **Przeznaczenie:** Diagnostyka frameworka – izolacja czystego narzutu HTTP, routingu i weryfikacji podpisu JWT w pamięci bez udziału bazy danych.
- **Odpowiedź (HTTP 200):**
  ```json
  {
    "status": "ok"
  }
  ```

#### EP1: `GET /api/tables` (Scenariusz S1 & S3)
- **Przeznaczenie:** Pomiar bazowy czystego odczytu prostej tabeli słownikowej.
- **Złożoność SQL:** 0 złączeń (pojedyncze zapytanie `SELECT ... FROM tables ORDER BY table_number LIMIT 20 OFFSET ?`).
- **Odpowiedź (HTTP 200):** Obiekt stronicowania zawierający 20 rekordów stolików.

#### EP2: `GET /api/menu-items` (Scenariusz S3)
- **Przeznaczenie:** Badanie narzutu szerokości hydratacji obiektów ORM na kolekcji rekordów.
- **Złożoność SQL:** 1 relacja (`MenuItem::with('dish')`) filtrowana po `is_available = true`. Eloquent wykonuje zapytanie bazowe oraz zapytanie eager loading `SELECT * FROM dishes WHERE id IN (...)`.
- **Wynik:** Hydratacja 20 obiektów `MenuItem` oraz 20 powiązanych encji `Dish` (łącznie 40 obiektów domenowych w pamięci).

#### EP3: `GET /api/orders` (Scenariusz S2)
- **Przeznaczenie:** Test skalowalności odczytu pod wysokim obciążeniem (200, 500, 1 000 VU).
- **Złożoność SQL:** 2 relacje eager load (`table`, `waiter`) z sortowaniem malejącym po dacie `ordered_at` i stronicowaniem (20 zamówień na stronę).

#### EP4: `GET /api/orders/{id}` (Scenariusz S3)
- **Przeznaczenie:** Badanie narzutu głębokości relacji (hierarchia obiektów).
- **Złożoność SQL:** 3-poziomowy nested eager loading:
  `$order->load(['table', 'waiter', 'orderItems.menuItem.dish'])`.
- **Wynik:** Pobranie pojedynczego zamówienia wraz ze stolikiem, kelnerem, listą pozycji zamówienia, powiązanymi pozycjami menu i daniami (~10 encji w grafie relacji).

#### EP5: `GET /api/dishes/{dish}/ingredients` (Rezerwa)
- **Przeznaczenie:** Odczyt relacji wiele-do-wielu (N:M) przez tabelę pośredniczącą `dish_ingredients`.
- **Złożoność SQL:** Pobranie składników dania z dołączeniem atrybutów pivota (`quantity`).

#### EP6: `GET /api/dashboard/summary` (Scenariusz S3)
- **Przeznaczenie:** Złożone zapytanie analityczne, w którym wąskim gardłem jest silnik relacyjny SQL, a nie serializacja ORM.
- **Złożoność SQL:**
  - 3 złączenia `INNER JOIN`: `order_items` -> `orders`, `order_items` -> `menu_items`, `menu_items` -> `dishes`.
  - Filtrowanie okna czasowego ostatnich 30 dni względem zamrożonej daty `BENCH_NOW` (33 469 zamówień).
  - Grupowanie `GROUP BY dishes.category`.
  - Funkcje agregujące: `COUNT(DISTINCT orders.id)`, `SUM(quantity)`, `SUM(revenue)`, `AVG(...)`.

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
- **Przebieg w `OrderService` (w ramach `DB::transaction`):**
  1. Sprawdzenie poprawności i istnienia stolika `tables`.
  2. Sprawdzenie dostępności wybranych pozycji `menu_items` (`is_available = true`).
  3. `INSERT` do tabeli `orders` ze statusem `open`.
  4. Wsadowe utworzenie rekordów `order_items` z cenami jednostkowymi pobranymi z bazy.
  5. Obliczenie sumy łącznej (`total_price`) i aktualizacja rekordu zamówienia.
- **Odpowiedź (HTTP 201):** Nowo utworzone zamówienie wraz z pozycjami.

#### EP8: `PATCH /api/orders/{id}/status` (Scenariusz S1)
- **Przeznaczenie:** Prosta operacja zapisu/modyfikacji w miejscu (*in-place update*).
- **Ciało żądania (JSON):**
  ```json
  {
    "status": "paid"
  }
  ```
- **Działanie:** Aktualizacja statusu zamówienia w bazie bez modyfikacji powiązanych encji.

#### EP9: `POST /api/reservations` (Rezerwa)
- **Przeznaczenie:** Tworzenie rezerwacji z walidacją kolizji terminów stolika na poziomie bazy danych.

---

## 4. Warstwy Aplikacji i Struktura Kodu

```
app/
├── Auth/
│   └── ClaimJwtGuard.php      # Niestandardowy guard JWT - bezstanowa resolucja usera in-memory
├── Enums/                     # Typowane enumy (OrderStatus, TableStatus, UserRole itp.)
├── Exceptions/
│   └── BusinessRuleException.php # Wyjątki biznesowe mapowane na kody HTTP 422
├── Http/
│   ├── Controllers/           # Kontrolery MVC (OrderController, TableController itp.)
│   ├── Middleware/
│   │   └── CountQueries.php   # Diagnostyka liczby zapytań SQL (nagłówek X-Debug-Queries)
│   └── Requests/              # Walidatory FormRequest (StoreOrderRequest itp.)
├── Models/                    # Modele Eloquent (Order, Table, Dish, MenuItem itp.)
├── Policies/
│   └── OrderPolicy.php        # Logika uprawnień (np. Waiter widzi tylko własne zamówienia)
└── Services/                  # Logika biznesowa (OrderService, DashboardService)
```

---

## 5. Uruchamianie i Diagnostyka

### Uruchomienie w środowisku Docker
Stos Laravel uruchamiany jest z poziomu katalogu głównego `benchmark/`:

```bash
# Uruchomienie bazy danych i stosu Laravel
docker compose --profile laravel up -d --build

# Sprawdzenie dostępności endpointu healthcheck
curl -i http://localhost:8080/up
```

### Inspekcja zapytań SQL (Diagnostyka S3)
Wysłanie żądania z nagłówkiem `X-Debug-Queries: true` zwraca w nagłówku odpowiedzi `X-Query-Count` liczbę instrukcji SQL wykonanych przez dany endpoint:

```bash
curl -i -H "Authorization: Bearer <TOKEN>" \
     -H "X-Debug-Queries: true" \
     http://localhost:8080/api/tables
```
*(Nagłówek `X-Query-Count: 1` pojawi się w odpowiedzi HTTP).*

---

## 6. Specyfikacja OpenAPI (Swagger)

Pełna, sformalizowana specyfikacja interfejsu API w standardzie **OpenAPI 3.0.3** znajduje się w pliku:
- [`openapi.yaml`](./openapi.yaml)

Zawiera ona szczegółowe schematy żądań, odpowiedzi, typów wyliczeniowych (Enum), nagłówków diagnostycznych oraz struktury kopert paginacji. Może być bezpośrednio importowana do narzędzi takich jak Swagger UI, Postman, Insomnia czy Redoc.

