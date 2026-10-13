# Benchmark Wydajnościowy: Laravel vs NestJS w Architekturze REST API

Kompleksowe środowisko eksperymentalne do empirycznego porównania wydajności frameworków **Laravel 13 (PHP 8.4)** oraz **NestJS 11 (Node.js 24 LTS)** w architekturze REST API, zrealizowane w kontrolowanym środowisku kontenerowym Docker z wykorzystaniem narzędzia Apache JMeter.

---

## Spis Treści

- [Dokumentacja Projektu (Indeks Dokumentów)](#dokumentacja-projektu-indeks-dokumentów)
1. [Wymagania sprzętowe i Szybki Start (Quick Start)](#1-wymagania-sprz%C4%99towe-i-szybki-start-quick-start)
2. [Architektura i Symetria Środowiska](#2-architektura-i-symetria-%C5%9Brodowiska)
3. [Struktura Repozytorium](#3-struktura-repozytorium)
4. [Konfiguracja Środowiska i Runtimów](#4-konfiguracja-%C5%9Brodowiska-i-runtim%C3%B3w)
5. [Determinizm Danych i Zarządzanie Bazą](#5-determinizm-danych-i-zarz%C4%85dzanie-baz%C4%85)
6. [Pipeline Wykonawczy i Orkiestracja Testów](#6-pipeline-wykonawczy-i-orkiestracja-test%C3%B3w)
7. [Przetwarzanie Wyników i Analiza Statystyczna](#7-przetwarzanie-wynik%C3%B3w-i-analiza-statystyczna)
8. [Narzędzia Diagnostyczne](#8-narz%C4%99dzia-diagnostyczne)

---

## Dokumentacja Projektu (Indeks Dokumentów)

Kompletna dokumentacja badania została podzielona na dedykowane moduły techniczne:

| Dokument | Ścieżka pliku | Zakres i zawartość |
| :--- | :--- | :--- |
| **Słownik Danych i Wyniki** | [`DATA_DICTIONARY.md`](file:///home/user/projekty/badanie/DATA_DICTIONARY.md) | Struktura katalogu `results/`, legenda nazewnictwa oraz pełna specyfikacja kolumn plików CSV i JSON (`results.jtl`, `stats.csv`, `meta.json`, `runs.csv`, `summary.csv`). |
| **Baza Danych** | [`DATABASE.md`](file:///home/user/projekty/badanie/DATABASE.md) | Schemat relacyjny PostgreSQL 16 (diagram ERD Mermaid), słowniki i tabele transakcyjne, deterministyczny seeder (`mt_srand(20260101)`) oraz mechanizmy migawek `*_template`. |
| **Skrypty i Pipeline** | [`SCRIPTS.md`](file:///home/user/projekty/badanie/SCRIPTS.md) | Dokumentacja orkiestracji eksperymentów (`run-main.sh`, `run-scenario.sh`), zarządzania stanem bazy (`db-setup.sh`, `db-reset.sh`), pakietu analizy statystycznej Bootstrap 10k (`summarize.py`) i testów dymnych. |
| **Aplikacja Laravel** | [`benchmark/apps/laravel-app/README.md`](file:///home/user/projekty/badanie/benchmark/apps/laravel-app/README.md) | Architektura stosu PHP 8.4 + OPcache/JIT, procesy PHP-FPM, uwierzytelnianie `ClaimJwtGuard`, specyfikacja endpointów EP1–EP10 oraz specyfikacja [OpenAPI 3.0](file:///home/user/projekty/badanie/benchmark/apps/laravel-app/openapi.yaml). |
| **Aplikacja NestJS** | [`benchmark/apps/nestjs-app/README.md`](file:///home/user/projekty/badanie/benchmark/apps/nestjs-app/README.md) | Architektura stosu Node.js 24 + PM2 Cluster Mode, konfiguracja TypeORM (`relationLoadStrategy: 'query'`), specyfikacja endpointów EP1–EP10 oraz specyfikacja [OpenAPI 3.0](file:///home/user/projekty/badanie/benchmark/apps/nestjs-app/openapi.yaml). |

## 1. Wymagania sprzętowe i Szybki Start (Quick Start)

### Wymagania sprzętowe i systemowe
- **Procesor:** Min. 12 vCPU.
- **Pamięć RAM:** Min. 16 GB RAM (zalecane $\ge 15.6$ GB przydzielone dla WSL2 / Linuksa).
- **System operacyjny:** Linux (Ubuntu 22.04 LTS) lub Windows 11 z WSL2 (jądro $\ge 6.6$).
- **Oprogramowanie:** Docker Engine $\ge 24.0$ z Docker Compose v2, Python 3.10+, Bash, `curl`, `jq`.

> **Zasada izolacji:** Podczas testów uruchomiony jest w danym momencie tylko **jeden stos aplikacyjny** (Laravel lub NestJS), dzięki czemu procesy nie konkurują o te same rdzenie procesora i pamięć RAM. Generator JMeter działa w dedykowanym kontenerze w sieci mostkowej Docker (`bridge`), nie obciążając budżetu CPU aplikacji.

### Szybki Start (Krok po kroku)

```bash
cd benchmark

# 1. Konfiguracja zmiennych środowiskowych
cp .env.example .env
# W razie potrzeby dostosuj hasła i klucze w .env

# 2. Inicjalizacja i zasilenie bazy danych (migracje + deterministyczny seeder + szablony *_template)
./scripts/db-setup.sh

# 3. Wygenerowanie danych pomocniczych dla planów JMeter (zakresy ID, stronicowanie)
./scripts/jmeter-data.sh

# 4. Uruchomienie pełnej serii pomiarowej (n=10 powtórzeń dla S1, S2, S2-pool1, S3)
./scripts/run-main.sh all

# Alternatywnie: uruchomienie pojedynczego scenariusza
./scripts/run-main.sh s1
```

Skrypt `scripts/run-main.sh` jest w pełni wznawialny (**resumable**): po przerwaniu pomija już ukończone powtórzenia (zweryfikowane sumą kontrolną w `meta.json`).

---

## 2. Architektura i Symetria Środowiska

Aby wyizolować narzut samych frameworków i ich modeli wykonawczych (synchroniczny PHP-FPM vs asynchroniczny Event Loop Node.js), wdrożono ścisłą symetrię architektoniczną:

| Warstwa / Komponent | Stos Laravel | Stos NestJS |
| :--- | :--- | :--- |
| **System bazowy obrazu** | Debian 12 Bookworm (`php:8.4-fpm-bookworm`) | Debian 12 Bookworm (`node:24-bookworm-slim`) |
| **Wersja platformy** | PHP 8.4 (OPcache + JIT tracing 128 MB) | Node.js 24.21.0 LTS |
| **Zarządca procesów** | PHP-FPM (`pm = static`, 4 procesy potomne) | PM2 Cluster Mode (4 instancje robocze) |
| **Przydział zasobów (cgroups)** | 4 vCPU, 2 GiB RAM | 4 vCPU, 2 GiB RAM |
| **Reverse Proxy** | Nginx 1.25 (FastCGI, brak logowania na dysk) | Nginx 1.25 (HTTP keepalive 64, brak logowania) |
| **Połączenia z bazą** | 1 stałe / worker (`PDO::ATTR_PERSISTENT`, 4 łącznie) | Pula 10 / worker (max 40); kontrola S2: 1 / worker (4 łącznie) |
| **Strategia ORM** | Eloquent (Active Record, relacje w osobnych zapytaniach) | TypeORM (`relationLoadStrategy: 'query'`, koperta stronicowania Laravel) |
| **Baza danych** | PostgreSQL 16 (4 vCPU, 2 GiB RAM, `max_connections = 100`, baza w RAM) | Identyczna baza sklonowana z szablonu |

---

## 3. Struktura Repozytorium

```
benchmark/
├── .env.example             # Szablon zmiennych środowiskowych
├── docker-compose.yml       # Definicja usług Docker z profilami (laravel, nestjs, setup, loadtest)
│
├── apps/
│   ├── laravel-app/         # Aplikacja backendowa Laravel 13
│   │   ├── Dockerfile       # Wielostopniowy build (target: app oraz tools)
│   │   ├── docker/          # opcache.ini, php-fpm.conf, entrypoint.sh
│   │   └── database/seeders/RestaurantSeeder.php # Deterministyczny seeder bazy
│   ├── nestjs-app/          # Aplikacja backendowa NestJS 11
│   │   ├── Dockerfile       # Multi-stage build (build -> production)
│   │   ├── ecosystem.config.js # Konfiguracja PM2 cluster mode (4 instancje)
│   │   └── src/             # Moduły, kontrolery, DTOs, TypeORM entities
│   └── nginx/               # Konfiguracje reverse proxy (laravel.conf, nestjs.conf)
│
├── jmeter/
│   ├── Dockerfile           # Kontener Apache JMeter 5.6.3 z CLI runnerem
│   ├── run.properties       # Globalne parametry wykonawcze JMeter
│   ├── s1.jmx               # Plan testowy Scenariusza S1 (Baseline CRUD)
│   ├── s2.jmx               # Plan testowy Scenariusza S2 (Stress / Scalability)
│   ├── s3.jmx               # Plan testowy Scenariusza S3 (Relational Complexity)
│   └── data/                # Wygenerowane pliki wejściowe (ranges.properties, csv)
│
├── scripts/                 # Narzędzia orkiestracji i analizy
│   ├── run-main.sh          # Główny runner serii pomiarowej (s1, s2, s2-pool1, s3, all)
│   ├── run-scenario.sh      # Niski poziom wykonawczy: warm-up, stats, interleaving, integrity
│   ├── db-setup.sh          # Jednorazowa inicjalizacja i migracja bazy + szablony
│   ├── db-reset.sh          # Szybkie przywracanie baz z szablonu template + restart aplikacji
│   ├── jmeter-data.sh       # Ekstrakcja parametrów danych z bazy dla planów JMeter
│   ├── summarize.py         # Skrypt analityczny: metryki, Bootstrap 10k CI, werdykty hipotez
│   ├── summarize_common.py  # Stałe progi hipotez, funkcje formatowania i indeksowania
│   ├── summarize_data.py    # Parsowanie surowych plików .jtl i docker stats
│   ├── summarize_stats.py   # Implementacja procedury Bootstrap i estymatorów OLS
│   ├── golden-write-check.sh# Weryfikacja determinizmu zapisu (EP7, EP8, EP9)
│   ├── sql-compare.sh       # Porównanie zapytań SQL generowanych przez Eloquent i TypeORM
│   └── query-count.sh       # Zliczanie zapytań SQL przez nagłówki X-Debug-Queries
│
└── results/                 # Wyniki pomiarów (struktura: <scenario>/<fw>/<ep>/vu<N>/rep<NN>/)
```

Szczegółowa dokumentacja poszczególnych podsystemów:
- [Aplikacja Laravel (`apps/laravel-app/README.md`)](file:///home/user/projekty/badanie/benchmark/apps/laravel-app/README.md) – architektura, OPcache/JIT, endpointy i specyfikacja [OpenAPI 3.0](file:///home/user/projekty/badanie/benchmark/apps/laravel-app/openapi.yaml).
- [Aplikacja NestJS (`apps/nestjs-app/README.md`)](file:///home/user/projekty/badanie/benchmark/apps/nestjs-app/README.md) – architektura, PM2 cluster mode, TypeORM, endpointy i specyfikacja [OpenAPI 3.0](file:///home/user/projekty/badanie/benchmark/apps/nestjs-app/openapi.yaml).
- [Skrypty wykonawcze i analityczne (`SCRIPTS.md`)](file:///home/user/projekty/badanie/SCRIPTS.md) – orkiestracja, parametry środowiskowe, procedury Bootstrap 10k i testy dymne.
- [Schemat i determinizm bazy danych (`DATABASE.md`)](file:///home/user/projekty/badanie/DATABASE.md) – diagram ERD Mermaid, schemat tabel PostgreSQL 16, seeder i mechanizmy szablonów `*_template`.
- [Słownik danych i formaty wyników (`DATA_DICTIONARY.md`)](file:///home/user/projekty/badanie/DATA_DICTIONARY.md) – struktura `results/`, legenda nazewnictwa oraz pełna specyfikacja kolumn plików CSV i JSON.

---

## 4. Konfiguracja Środowiska i Runtimów

### Plik `.env`
Parametry sterujące konfiguracją infrastruktury:
- `BENCH_NOW="2026-09-01 00:00:00"`: Zamrożony znacznik czasu odniesienia, gwarantujący identyczność generowanych danych i agregacji EP6.
- `JWT_SECRET`, `JWT_TTL=3600`: Współdzielony klucz HS256 i czas życia tokenu (164-bajtowy token JWT).
- `APP_CPUS=4`, `APP_MEMORY=2g`: Limity cgroups dla kontenerów aplikacji.
- `DB_CPUS=4`, `DB_MEMORY=2g`: Zasoby przydzielone dla PostgreSQL.
- `DB_POOL_SIZE=10`: Rozmiar puli połączeń na proces roboczy w NestJS (w serii kontrolnej S2-pool1 nadpisywany dynamicznie na `1`).

### Optymalizacje produkcyjne silników
1. **Laravel (PHP-FPM):**
   - `opcache.ini`: włączony OPcache, JIT w trybie `tracing` z buforem 128 MB (`opcache.jit_buffer_size=128M`), wyłączona walidacja znaczników czasu plików (`opcache.validate_timestamps=0`).
   - `php-fpm.conf`: sztywny procesor `pm = static`, `pm.max_children = 4`, wyłączone logowanie dostępu do plików.
   - `entrypoint.sh`: automatyczne generowanie zoptymalizowanych map klas (`composer dump-autoload --classmap-authoritative`) oraz pamięci podręcznej tras i konfiguracji (`config:cache`, `route:cache`).
2. **NestJS (Node.js):**
   - `ecosystem.config.js`: uruchomienie w trybie klastra PM2 (`exec_mode: 'cluster'`, `instances: 4`).
   - Kompilacja ze statycznym drzewem wyjściowym (`nest build`), wykluczenie zależności developerskich (`NODE_ENV=production`).
3. **Nginx:**
   - Wyłączone logi dostępu (`access_log off`) zapobiegają asymetrii I/O dysku.
   - Pule keepalive dla NestJS i FastCGI dla PHP-FPM bez blokowania bezczynnych procesów.
4. **PostgreSQL 16:**
   - Jawnie zdefiniowane parametry: `max_connections = 100` (bezpieczny margines powyżej 40 połączeń NestJS i 4 PHP-FPM), `shared_buffers = 128MB`, `work_mem = 4MB`, rozszerzenie `pg_stat_statements`.

---

## 5. Determinizm Danych i Zarządzanie Bazą

> Szczegółowy opis schematu relacyjnego, relacji 1:N / N:M, diagramu ERD oraz procedur seedera znajduje się w dedykowanym dokumencie [`DATABASE.md`](file:///home/user/projekty/badanie/DATABASE.md).

### Generator danych (`RestaurantSeeder.php`)
- **Ziarno generatora liczb pseudolosowych:** Ustalony seed `mt_srand(20260101)` i `fake()->seed(20260101)`.
- **Rozmiary tabel:**
  - Tabele słownikowe: `users` (200), `tables` (200), `ingredients` (200), `dishes` (500), `menu_items` (500).
  - Tabela asocjacyjna: `dish_ingredients` (2 000 wierszy, relacja N:M).
  - Tabele transakcyjne: `orders` (100 000 wierszy), `order_items` (dokładnie **299 695** wierszy; liczba pozycji na zamówienie wyznaczana z rozkładu jednostajnego `mt_rand(1, 5)`).
- **Deterministyczna agregacja (EP6):** Zapytanie dashboardu agreguje transakcje z ostatnich 30 dni przed znacznikiem `BENCH_NOW` (dokładnie 33 469 zamówień), co zapewnia bajtowo identyczne odpowiedzi w każdym powtórzeniu.

### Procedura tworzenia i resetu baz danych
1. `scripts/db-setup.sh`:
   - Migruje i zasila bazę `laravel_app`.
   - Klonuje strukturę i dane do bazy `nestjs_app` poleceniem `CREATE DATABASE nestjs_app TEMPLATE laravel_app`.
   - Tworzy migawki wzorcowe: `laravel_app_template` oraz `nestjs_app_template`.
2. `scripts/db-reset.sh`:
   - Wywoływany automatycznie przed każdym pojedynczym powtórzeniem pomiarowym.
   - Odtwarza czystą bazę w kilka sekund z szablonu (`DROP DATABASE ...; CREATE DATABASE ... TEMPLATE ..._template`).
   - Restartuje kontenery aplikacji i proxy w celu wyczyszczenia pamięci podręcznych procesów (V8 TurboFan, OPcache, pule połączeń).

---

## 6. Pipeline Wykonawczy i Orkiestracja Testów

> Szczegółowy opis działania skryptów orkiestracyjnych, parametrów wykonawczych i flag środowiskowych znajduje się w [`SCRIPTS.md`](file:///home/user/projekty/badanie/SCRIPTS.md).

### Plany Apache JMeter (`.jmx`)
- **Tryb obciążenia:** Pętla zamknięta (**closed workload**) bez opóźnień użytkownika (*zero think time*) z połączeniami HTTP persistent keep-alive.
- **Grupa `setUp`:** Pojedynczy wątek przed startem fazy pomiarowej wykonuje zapytanie uwierzytelniające (`POST /api/auth/login`, EP10) i pobiera token JWT współdzielony przez wszystkie wątki wirtualne.
- **Pliki parametrów:** `scripts/jmeter-data.sh` generuje `jmeter/data/ranges.properties` (maksymalne zakresy stron zapobiegające błędom 404) oraz `available_menu_items.csv`.

### Algorytm orkiestracji (`scripts/run-scenario.sh`)
Dla każdego endpointu, poziomu współbieżności i powtórzenia:
1. **Algorytm przeplotu (Interleaving):** W pętli powtórzeń ($n = 1..10$) kolejność uruchamiania frameworków jest pseudolosowo mieszana w oparciu o stałe ziarno `INTERLEAVE_SEED=20261002` + numer powtórzenia. Zapobiega to faworyzowaniu któregokolwiek rozwiązania przez nagrzewanie procesora (*thermal throttling*) lub dryft obciążenia maszyny.
2. **Faza rozgrzewki (Warm-Up):** 
   - 60 s dla S1 i S3; 120 s dla S2.
   - Pozwala zoptymalizować kod maszynowy przez silniki JIT (V8 TurboFan i PHP OPcache/JIT). Próbki z tej fazy są odrzucane.
3. **Faza pomiarowa (Measurement):**
   - 60 s dla S1 i S3; 120 s dla S2.
   - Pierwsze 10 s (ramp-up wątków) jest obcinane z analizy statystycznej w celu badania wyłącznie stanu ustalonego (*steady-state*).
4. **Próbkowanie zasobów (`docker stats`):**
   - Ciągły streaming zużycia CPU i pamięci (dla aplikacji, Nginx, PostgreSQL i JMeter) w odstępach $\sim 0.5$ s zapisywany do `stats.csv`.
5. **Bramki integralności zapisu (Integrity Gates):**
   - Dla operacji odczytu weryfikowana jest niezmienniczość liczby wierszy w bazie.
   - Dla tworzenia zamówień (EP7) sprawdzana jest ścisła zgodność liczby wstawionych wierszy w `orders` i `order_items` z liczbą kodów HTTP 201 (stosunek 1:1). Niezgodność skutkuje unieważnieniem biegu.

---

## 7. Przetwarzanie Wyników i Analiza Statystyczna

> Pełna specyfikacja kolumn plików wynikowych, schematy obiektów `meta.json` oraz legenda struktury katalogów znajdują się w [`DATA_DICTIONARY.md`](file:///home/user/projekty/badanie/DATA_DICTIONARY.md).

Analiza danych pomiarowych jest wykonywana przez pakiet `scripts/summarize.py`:

```bash
# Podsumowanie i ocena hipotez wybranego scenariusza
python3 scripts/summarize.py s1
python3 scripts/summarize.py s2
python3 scripts/summarize.py s2-pool1
python3 scripts/summarize.py s3
```

### Gromadzone metryki
- **Czasy odpowiedzi:** Mediana ($p_{50}$), 95. percentyl ($p_{95}$) i 99. percentyl ($p_{99}$) wyznaczane metodą *nearest-rank* z surowych śladów `.jtl`.
- **Przepustowość:** Liczba udanych żądań na sekundę (RPS).
- **Wskaźnik błędów:** Procent żądań zakończonych kodem HTTP innym niż 200/201 lub przekroczeniem 30-sekundowego limitu czasu.
- **Zużycie zasobów:** Średnie i szczytowe zużycie CPU% i RAM (MiB) z `docker stats`.
- **Metryki uzupełniające:**
  - Średni czas opóźnienia z Prawa Little’a ($R \approx N / X$) – ciągła metryka omijająca 1-ms kwantowanie JMetera.
  - Czas CPU na żądanie (*CPU time per request*) – oddziela wydajność algorytmiczną od opóźnień kolejkowania.

### Weryfikacja hipotez badawczych

#### 1. Reguła poprawności niskiego obciążenia (*Low-Load Validity Rule*)
Poziom współbieżności $N$ kwalifikuje się do werdyktu niskiego obciążenia (H1: 1, 2 VU; H3: 2 VU), jeśli dla obu frameworków i wszystkich endpointów:
- Współczynnik skalowania przepustowości $X(N) / (N \cdot X(1)) \ge 0.80$,
- Średnie obciążenie CPU aplikacji $< 80\%$ limitu kontenera ($< 320\%$ dla 4 vCPU),
- Średnie obciążenie CPU bazy PostgreSQL $< 80\%$ limitu kontenera ($< 320\%$).

#### 2. Procedura Bootstrap i Reguły Decyzyjne
Dla $n = 10$ median powtórzeń generowane jest **10 000 próbkowania bootstrap** (z ustalonym seedem `BOOTSTRAP_SEED = 20261002`):
- **H1 (Równoważność w S1 na EP1 i EP8):**
  $$\Delta p_{95} = \frac{|p_{95,L} - p_{95,N}|}{(p_{95,L} + p_{95,N}) / 2} \times 100\%$$
  Hipoteza **potwierdzona**, gdy górna granica 95% przedziału ufności $\Delta p_{95} \le 15\%$ przy błędach $< 1\%$.
- **H2 (Degradacja w S2 pod stresem na EP3):**
  $$r = \frac{s_L}{s_N}$$
  gdzie $s_L, s_N$ to nachylenia regresji liniowej (OLS) opóźnienia $p_{95}$ względem współbieżności $N \in \{200, 500, 1000\}$. Hipoteza **potwierdzona**, gdy dolna granica 95% CI wskaźnika $r > 1$ (szybsza degradacja Laravel).
- **H3 (Narzut relacji w S3):**
  Estymator Difference-in-Differences względem bazy jedno-tabelowej (EP1):
  $$D_k = (p_{95,L}(k) - p_{95,N}(k)) - (p_{95,L}(\text{EP1}) - p_{95,N}(\text{EP1}))$$
  Dla EP2 (szerokość relacji) hipoteza **potwierdzona**, jeśli przy 2 VU dolna granica 95% CI $D_{\text{EP2}} > 2\text{ ms}$ oraz estymator punktowy $D_{\text{EP2}} > 0$ przy 1 VU.

---

## 8. Narzędzia Diagnostyczne

W katalogu `scripts/` znajdują się pomocnicze skrypty ułatwiające inspekcję środowiska:
- **`scripts/golden-write-check.sh <laravel|nestjs>`:** Wykonuje deterministyczne żądania zapisu (EP7, EP8, EP9) i zrzuca wstawione encje z bazy w formacie JSON oraz statystyki z `pg_stat_statements`, umożliwiając porównanie 1:1 zachowania obu ORM.
- **`scripts/sql-compare.sh`:** Porównuje zapytania SQL generowane przez Eloquent i TypeORM dla każdego endpointu.
- **`scripts/query-count.sh`:** Wysyła żądania diagnostyczne z nagłówkiem `X-Debug-Queries` i sprawdza liczbę instrukcji SQL raportowaną w nagłówku odpowiedzi `X-Query-Count`.