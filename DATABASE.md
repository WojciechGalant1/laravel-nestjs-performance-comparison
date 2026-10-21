# Dokumentacja Bazy Danych (PostgreSQL 16) — Benchmark REST API

Niniejszy dokument przedstawia pełną specyfikację relacyjnej bazy danych **PostgreSQL 16** wykorzystywanej w empirycznym badaniu porównawczym wydajności frameworków **Laravel 13 (PHP 8.4)** oraz **NestJS 11 (Node.js 24 LTS)**.

Baza danych modeluje realistyczny system zarządzania restauracją (POS / Restaurant Management System), obejmując tabele słownikowe, asocjacyjne oraz transakcyjne o łącznym wolumenie od **402 tys. do ponad 502 tys. rekordów** (w zależności od wariantu badania).

---

> ### 📌 Rozróżnienie Zakresu Badania: Artykuł Naukowy vs Praca Magisterska
> 
> W repozytorium występuje celowe rozróżnienie pomiędzy zakresem bazy danych wykorzystanym w **artykule naukowym** a pełnym zakresem przygotowanym pod **pracę magisterską**:
> 
> | Wymiar | Artykuł Naukowy (konferencyjny / 8 stron) | Praca Magisterska (pełny zakres repozytorium) |
> | :--- | :--- | :--- |
> | **Liczba tabel** | **8 tabel** (słowniki, pivot, `orders`, `order_items`) | **9 tabel** (+ tabela `reservations`) |
> | **Liczba rekordów** | **401 895 wierszy** (~402 tys.) | **501 895 wierszy** (+100 000 wierszy w `reservations`) |
> | **Typy indeksów** | Standardowe indeksy **B-Tree** (klucze obce, unikalne i pola zapytań) | B-Tree + **GiST** (rozszerzenie `btree_gist`, ograniczenie `EXCLUDE USING gist`) |
> | **Obsługiwane endpointy** | **EP1, EP2, EP3, EP5, EP7** (oraz pomocniczo EP4, EP6, login EP0) | **Wszystkie endpointy EP0–EP9** (w tym EP8 N:M pivot oraz EP9 rezerwacje) |
> | **Uzasadnienie metodyczne** | Rygor objętościowy publikacji (8 stron) oraz izolacja ogona opóźnień $p_{95}$ od zaawansowanych blokad czasowych w bazie. | Pełna ewaluacja architektury: relacje N:M, transakcje ACID, blokady wierszy oraz typy przedziałowe (`tsrange`). |

---

## Spis Treści
1. [Diagram Związków Encji (ERD)](#1-diagram-zwi%C4%85zk%C3%B3w-encji-erd)
2. [Typy Danych i Rozszerzenia PostgreSQL](#2-typy-danych-i-rozszerzenia-postgresql)
3. [Szczegółowa Specyfikacja Tabel i Relacji](#3-szczeg%C3%B3%C5%82owa-specyfikacja-tabel-i-relacji)
4. [Determinizm Generowania Danych (Seeding)](#4-determinizm-generowania-danych-seeding)
5. [Zarządzanie Bazami Danych i Mechanizm Szablonów (Templates)](#5-zarz%C4%85dzanie-bazami-danych-i-mechanizm-szablon%C3%B3w-templates)
6. [Mapowanie Tabel na Endpointy i Scenariusze Badawcze](#6-mapowanie-tabel-na-endpointy-i-scenariusze-badawcze)
7. [Konfiguracja Silnika PostgreSQL 16](#7-konfiguracja-silnika-postgresql-16)

---

## 1. Diagram Związków Encji (ERD)

```mermaid
erDiagram
    users ||--o{ orders : "places / serves"
    tables ||--o{ orders : "assigned to"
    tables ||--o{ reservations : "reserved for"
    dishes ||--o{ menu_items : "offered as"
    dishes ||--o{ dish_ingredients : "composed of"
    ingredients ||--o{ dish_ingredients : "used in"
    orders ||--|{ order_items : "contains"
    menu_items ||--o{ order_items : "selected in"

    users {
        bigint id PK "200 rows"
        varchar first_name
        varchar last_name
        varchar email UK
        varchar password
        user_role role
        timestamp created_at
        timestamp updated_at
    }

    tables {
        bigint id PK "200 rows"
        int table_number UK
        int capacity
        table_status status
        timestamp created_at
        timestamp updated_at
    }

    ingredients {
        bigint id PK "200 rows"
        varchar name
        varchar unit
        timestamp created_at
        timestamp updated_at
    }

    dishes {
        bigint id PK "500 rows"
        varchar name
        dish_category category
        timestamp created_at
        timestamp updated_at
    }

    dish_ingredients {
        bigint id PK "2 000 rows (pivot)"
        bigint dish_id FK
        bigint ingredient_id FK
        decimal quantity
        timestamp created_at
        timestamp updated_at
    }

    menu_items {
        bigint id PK "500 rows"
        bigint dish_id FK
        decimal price
        boolean is_available
        timestamp created_at
        timestamp updated_at
    }

    orders {
        bigint id PK "100 000 rows"
        bigint table_id FK
        bigint user_id FK
        order_status status
        decimal total_price
        timestamp ordered_at
        timestamp created_at
        timestamp updated_at
    }

    order_items {
        bigint id PK "299 695 rows"
        bigint order_id FK
        bigint menu_item_id FK
        int quantity
        decimal unit_price
        text notes
        order_item_status status
        timestamp created_at
        timestamp updated_at
    }

    reservations {
        bigint id PK "100 000 rows (praca mgr)"
        bigint table_id FK
        varchar customer_name
        varchar phone_number
        date reservation_date
        time reservation_time
        int party_size
        int duration_minutes
        reservation_status status
        text notes
        timestamp created_at
        timestamp updated_at
    }
```

---

## 2. Typy Danych i Rozszerzenia PostgreSQL

Baza danych wykorzystuje natywne typy wyliczeniowe (`ENUM`) oraz dedykowane rozszerzenia systemowe PostgreSQL:

### Rozszerzenia
- **`btree_gist`**: Umożliwia indeksowanie standardowych typów danych (np. `bigint`) w strukturach GiST, co jest wymagane do obsługi wielokolumnowego ograniczenia wykluczającego `EXCLUDE USING gist` w tabeli `reservations`.
- **`pg_stat_statements`**: Śledzenie statystyk wykonania zapytań SQL i czasu planowania/wykonania na potrzeby testów diagnostycznych.

### Typy Wyliczeniowe (PostgreSQL Enums)
```sql
CREATE TYPE user_role AS ENUM ('manager', 'waiter');
CREATE TYPE table_status AS ENUM ('available', 'occupied', 'reserved', 'cleaning');
CREATE TYPE dish_category AS ENUM ('starter', 'main', 'dessert', 'drink', 'side');
CREATE TYPE order_status AS ENUM ('open', 'paid', 'cancelled');
CREATE TYPE order_item_status AS ENUM ('pending', 'in_progress', 'completed', 'cancelled');
CREATE TYPE reservation_status AS ENUM ('pending', 'confirmed', 'cancelled');
```

---

## 3. Szczegółowa Specyfikacja Tabel i Relacji

### 3.1. Tabele Słownikowe (Dictionary Entities)

Tabele słownikowe posiadają stałe, niewielkie rozmiary, co gwarantuje, że zapytania `SELECT` są zdominowane przez narzut frameworka i hydratację ORM, a nie buforowanie dyskowe.

#### `users` (200 wierszy)
Reprezentuje personel restauracji (menedżerów i kelnerów).
- `id` (`bigint`, PK, autoincrement)
- `first_name` (`varchar(255)`)
- `last_name` (`varchar(255)`)
- `email` (`varchar(255)`, UNIQUE)
- `password` (`varchar(255)`) – zahashowane hasło (`bcrypt`)
- `role` (`user_role`, domyślnie `'waiter'`)
- `created_at`, `updated_at` (`timestamp`)

#### `tables` (200 wierszy)
Stoliki restauracyjne.
- `id` (`bigint`, PK, autoincrement)
- `table_number` (`integer`, UNIQUE) – numer stolika (1–200)
- `capacity` (`integer`) – liczba miejsc (2, 4, 6, 8)
- `status` (`table_status`, domyślnie `'available'`)
- `created_at`, `updated_at` (`timestamp`)
- **Indeksy:** `tables_status_index` na kolumnie `status`.

#### `ingredients` (200 wierszy)
Składniki wykorzystywane w kuchni.
- `id` (`bigint`, PK, autoincrement)
- `name` (`varchar(255)`)
- `unit` (`varchar(50)`) – jednostka miary (np. `'g'`, `'ml'`, `'szt'`)
- `created_at`, `updated_at` (`timestamp`)

#### `dishes` (500 wierszy)
Katalog potraw oferowanych przez restaurację.
- `id` (`bigint`, PK, autoincrement)
- `name` (`varchar(255)`)
- `category` (`dish_category`) – kategoria potrawy (`starter`, `main`, `dessert`, `drink`, `side`)
- `created_at`, `updated_at` (`timestamp`)

#### `menu_items` (500 wierszy)
Pozycje w menu restauracji powiązane z daniami.
- `id` (`bigint`, PK, autoincrement)
- `dish_id` (`bigint`, FK $\rightarrow$ `dishes.id`, ON DELETE CASCADE)
- `price` (`decimal(8,2)`) – cena w menu
- `is_available` (`boolean`, domyślnie `true`) – dostępność danej pozycji
- `created_at`, `updated_at` (`timestamp`)
- **Indeksy:** `menu_items_dish_id_index`, `menu_items_is_available_index`.

---

### 3.2. Tabela Asocjacyjna / Pivot (Relacja N:M)

#### `dish_ingredients` (2 000 wierszy)
Tabela pośrednicząca modelująca skład każdego dania (średnio 4 składniki na danie).
- `id` (`bigint`, PK, autoincrement)
- `dish_id` (`bigint`, FK $\rightarrow$ `dishes.id`, ON DELETE CASCADE)
- `ingredient_id` (`bigint`, FK $\rightarrow$ `ingredients.id`, ON DELETE CASCADE)
- `quantity` (`decimal(8,2)`) – ilość składnika
- `created_at`, `updated_at` (`timestamp`)
- **Indeksy i Więzy:**
  - `dish_ingredients_dish_id_index`, `dish_ingredients_ingredient_id_index`
  - UNIQUE `(dish_id, ingredient_id)` – zapobiega duplikatom składników w daniu.

---

### 3.3. Tabele Transakcyjne (Transactional Records)

#### `orders` (100 000 wierszy)
Główna tabela transakcyjna przechowująca złożone zamówienia.
- `id` (`bigint`, PK, autoincrement)
- `table_id` (`bigint`, FK $\rightarrow$ `tables.id`, ON DELETE CASCADE)
- `user_id` (`bigint`, FK $\rightarrow$ `users.id`, NULLABLE, ON DELETE CASCADE) – kelner obsługujący
- `status` (`order_status`, domyślnie `'open'`) – status zamówienia (`open`, `paid`, `cancelled`)
- `total_price` (`decimal(10,2)`, domyślnie `0.00`) – kwota łączna
- `ordered_at` (`timestamp`, domyślnie `CURRENT_TIMESTAMP`) – czas złożenia zamówienia
- `created_at`, `updated_at` (`timestamp`)
- **Indeksy:**
  - `orders_table_id_index`
  - `orders_user_id_index`
  - `orders_status_index`
  - `orders_ordered_at_index` (kluczowy dla wydajności filtrowania zakresu dat w EP6).

#### `order_items` (dokładnie 299 695 wierszy)
Pozycje składające się na poszczególne zamówienia (1 do 5 pozycji na zamówienie).
- `id` (`bigint`, PK, autoincrement)
- `order_id` (`bigint`, FK $\rightarrow$ `orders.id`, ON DELETE CASCADE)
- `menu_item_id` (`bigint`, FK $\rightarrow$ `menu_items.id`, ON DELETE CASCADE)
- `quantity` (`integer`) – zamawiana liczba sztuk
- `unit_price` (`decimal(8,2)`) – cena jednostkowa w momencie zamówienia
- `notes` (`text`, NULLABLE) – uwagi klienta (np. "bez cebuli")
- `status` (`order_item_status`, domyślnie `'pending'`)
- `created_at`, `updated_at` (`timestamp`)
- **Indeksy:**
  - `order_items_order_id_index`
  - `order_items_menu_item_id_index`
  - `order_items_status_index`.

#### `reservations` (100 000 wierszy) — *[Wyłącznie Praca Magisterska; Wyłączona z Artykułu]*
Rezerwacje stolików z kontrolą kolizji czasowych. Tabela i powiązany endpoint EP9 zostały **wyłączone z serii pomiarowej artykułu naukowego**, aby zachować spójność z 8-stronicowym limitem publikacji i uniknąć wpływu zaawansowanych blokad silnika PostgreSQL na ogon opóźnień $p_{95}$. W pełnej pracy magisterskiej stanowi podstawę badania operacji ze złożonymi ograniczeniami integralności.
- `id` (`bigint`, PK, autoincrement)
- `table_id` (`bigint`, FK $\rightarrow$ `tables.id`, ON DELETE CASCADE)
- `customer_name` (`varchar(255)`)
- `phone_number` (`varchar(20)`)
- `reservation_date` (`date`)
- `reservation_time` (`time`)
- `party_size` (`integer`)
- `duration_minutes` (`integer`, domyślnie 120)
- `status` (`reservation_status`, domyślnie `'pending'`)
- `notes` (`text`, NULLABLE)
- `created_at`, `updated_at` (`timestamp`)
- **Więzy Integralności (Constraint):**
  ```sql
  ALTER TABLE reservations
  ADD CONSTRAINT reservations_no_overlap
  EXCLUDE USING gist (
      table_id WITH =,
      tsrange(
          (reservation_date + reservation_time),
          (reservation_date + reservation_time + make_interval(mins => duration_minutes))
      ) WITH &&
  ) WHERE (status <> 'cancelled');
  ```
  Zapewnia na poziomie silnika relacyjnego, że żaden stolik nie może posiadać nakładających się rezerwacji w tym samym przedziale czasowym (naruszenie zwraca kod błędu SQLSTATE `23P01`).

---

## 4. Determinizm Generowania Danych (Seeding)

W celu zapewnienia pełnej powtarzalności eksperymentu baza danych generowana jest w sposób ściśle deterministyczny przez seeder `RestaurantSeeder.php`:

1. **Ustalony Seed PRNG:**
   - Generator pseudolosowy inicjalizowany jest stałym ziarnem: `mt_srand(20260101)` oraz `fake()->seed(20260101)`.
   - Gwarantuje to identyczne wartości kluczy obcych, cen, statusów i nazw we wszystkich środowiskach.
2. **Rozkład pozycji w zamówieniach:**
   - Każde ze 100 000 zamówień losuje liczbę pozycji z rozkładu jednostajnego $U(1, 5)$ za pomocą `mt_rand(1, 5)`.
   - Wynikiem jest dokładnie **299 695 wierszy** w tabeli `order_items` (średnio 2.997 pozycji na zamówienie).
3. **Zamrożony Znacznik Czasu (`BENCH_NOW`):**
   - Wszystkie daty zamówień `orders.ordered_at` generowane są w oknie 90 dni wstecz od zamrożonego znacznika referencyjnego:
     ```env
     BENCH_NOW="2026-09-01 00:00:00"
     ```
   - Dzięki temu zapytanie dashboardu (EP6), które agreguje ostatnie 30 dni przed `BENCH_NOW`, obejmuje niezmiennie dokładnie **33 469 zamówień** niezależnie od daty i godziny uruchomienia benchmarku, zapewniając bajtowo identyczne odpowiedzi.
4. **Rozmiar i Pamięć RAM:**
   - Całkowity rozmiar danych w PostgreSQL wynosi ok. 150 MB dla wariantu 8 tabel (artykuł) i ok. 185 MB dla wariantu 9 tabel (praca mgr) wraz z indeksami, co z zapasem mieści się w przydzielonym limicie RAM kontenera PostgreSQL (2 GiB).
   - Eliminuje to wpływ wąskich gardeł związanych z fizycznymi operacjami I/O dysku.

---

## 5. Zarządzanie Bazami Danych i Mechanizm Szablonów (Templates)

Eksperyment wymaga, aby każde powtórzenie pomiarowe zaczynało się z dokładnie tego samego stanu początkowego, a modyfikacje generowane przez żądania zapisu (EP7, EP8, EP9) nie kumulowały się.

Zrealizowano to za pomocą mechanizmu szablonów PostgreSQL (`TEMPLATE`):

```
                   [ Inicjalizacja: db-setup.sh ]
                                  │
                  Migracja i Seeding (Laravel Tools)
                                  │
                                  ▼
                            laravel_app
                                  │
          ┌───────────────────────┴───────────────────────┐
          ▼                                               ▼
CREATE DATABASE ...                             CREATE DATABASE ...
TEMPLATE laravel_app                            TEMPLATE laravel_app
          │                                               │
          ▼                                               ▼
 laravel_app_template                                 nestjs_app
                                                          │
                                                          ▼
                                                 CREATE DATABASE ...
                                                 TEMPLATE nestjs_app
                                                          │
                                                          ▼
                                                  nestjs_app_template
```

### Procedura Krok po Kroku:
1. **`scripts/db-setup.sh` (Jednorazowo):**
   - Wykonuje migracje i seedera na bazie `laravel_app`.
   - Klonuje `laravel_app` do bazy `nestjs_app`.
   - Tworzy migawki wzorcowe: `laravel_app_template` oraz `nestjs_app_template`.
2. **`scripts/db-reset.sh` (Przed każdym powtórzeniem $n=1..10$):**
   - Usuwa bazę roboczą i błyskawicznie odtwarza ją z szablonu w kilka sekund:
     ```sql
     SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'laravel_app' AND pid <> pg_backend_pid();
     DROP DATABASE IF EXISTS laravel_app;
     CREATE DATABASE laravel_app TEMPLATE laravel_app_template;
     ```
   - Restartuje kontenery aplikacji i proxy w celu wyczyszczenia stanów pamięci podręcznej i pul połączeń.
3. **`scripts/jmeter-data.sh`:**
   - Eksportuje z bazy `laravel_app_template` aktualne zakresy identyfikatorów (`ranges.properties`) oraz dostępne pozycje menu (`available_menu_items.csv`), gwarantując brak błędów 404 w testach losowych.

---

## 6. Mapowanie Tabel na Endpointy i Scenariusze Badawcze

| Endpoint | Metoda | Wykorzystywane Tabele | Typ Operacji SQL | Rola w Badaniu | Zakres Badania |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EP0** | `POST /api/auth/login` | `users` | `SELECT ... WHERE email = ?` | Pre-test setup (wydanie JWT) | **Artykuł + Praca mgr** |
| **EP1** | `GET /api/tables` | `tables` | Prosty `SELECT ... LIMIT 20` | S1 (werdykt), S3 (baza odniesienia) | **Artykuł + Praca mgr** |
| **EP2** | `GET /api/menu-items` | `menu_items`, `dishes` | Eager load 1 relacji (`SELECT IN`) | S3 (główny werdykt narzutu szerokości) | **Artykuł + Praca mgr** |
| **EP3** | `GET /api/orders` | `orders`, `tables`, `users` | Eager load 2 relacji z filtrem `user_id` | S2 (główny werdykt skalowalności) | **Artykuł + Praca mgr** |
| **EP4** | `GET /api/orders/{id}` | `orders`, `tables`, `users`, `order_items`, `menu_items`, `dishes` | 3-poziomowy nested eager loading | S3 (obserwacja głębokości drzewa) | **Artykuł + Praca mgr** |
| **EP5** | `PATCH /api/orders/{id}/status` | `orders` | Prosty `UPDATE status = 'paid'` | S1 (werdykt zapisu bazowego) | **Artykuł + Praca mgr** |
| **EP6** | `GET /api/dashboard/summary` | `order_items`, `orders`, `menu_items`, `dishes` | 3 JOIN + `GROUP BY` + `COUNT`/`SUM`/`AVG` | S3 (obserwacja wąskiego gardła w SQL) | **Artykuł + Praca mgr** |
| **EP7** | `POST /api/orders` | `tables`, `menu_items`, `orders`, `order_items` | Transakcyjny `INSERT` (walidacja + 2 tabele) | S2 (obserwacja zapisu pod obciążeniem) | **Artykuł + Praca mgr** |
| **EP8** | `GET /api/dishes/{id}/ingredients` | `dishes`, `dish_ingredients`, `ingredients` | Relacja N:M z atrybutami pivota | Analiza relacji wiele-do-wielu | **Wyłącznie Praca mgr** |
| **EP9** | `POST /api/reservations` | `tables`, `reservations` | `INSERT` z walidacją `EXCLUDE USING gist` | Zapis ze złożonym indeksem GiST | **Wyłącznie Praca mgr** |
| **PING**| `GET /api/ping` | *Brak (0 DB)* | Weryfikacja podpisu JWT w pamięci | Diagnostyka izolowanego narzutu HTTP/JWT | **Artykuł + Praca mgr** |

---

## 7. Konfiguracja Silnika PostgreSQL 16

W pliku `benchmark/docker-compose.yml` zdefiniowano następujące parametry kontenera bazy danych:

```yaml
postgres:
  image: postgres:16-bookworm
  command:
    - postgres
    - -c
    - max_connections=100
    - -c
    - shared_buffers=128MB
    - -c
    - work_mem=4MB
    - -c
    - effective_cache_size=4GB
    - -c
    - shared_preload_libraries=pg_stat_statements
  volumes:
    - pgdata:/var/lib/postgresql/data
  cpus: 4
  mem_limit: 2g
```

### Uzasadnienie Konfiguracji:
- **`cpus: 4`, `mem_limit: 2g`**: Sztywny limit cgroups zapewniający izolację zasobów – baza nie konkuruje o zasoby z aplikacją ani generatorem JMeter.
- **`max_connections = 100`**: Bezpieczny limit znacznie przewyższający maksymalną liczbę połączeń obu aplikacji (NestJS: 4 workerów $\times$ 10 połączeń = 40; Laravel: 4 workerów $\times$ 1 połączenie = 4). Zapobiega to wyczerpaniu puli połączeń w teście warunków skrajnych S2 (1 000 VU).
- **Wolumen nazwany `pgdata`**: Dedykowany wolumen Docker eliminuje narzut translacji systemu plików WSL2/Windows, gwarantując maksymalną wydajność I/O silnika PostgreSQL.
