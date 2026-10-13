# Dokumentacja Skryptów i Pipeline'u Pomiarowego

Kompleksowa dokumentacja techniczna narzędzi automatyzacji, orkiestracji eksperymentów, zbierania metryk telemetrycznych oraz rygorystycznej analizy statystycznej w projekcie empirycznego porównania wydajności frameworków **Laravel** i **NestJS**.

Wszystkie skrypty znajdują się w katalogu [`benchmark/scripts/`](file:///home/user/projekty/badanie/benchmark/scripts/) i są w pełni przystosowane do autonomicznego uruchamiania w środowisku Linux oraz WSL2 (Ubuntu 22.04+).

---

## Spis Treści

1. [Architektura Pipeline'u i Przepływ Danych](#1-architektura-pipelineu-i-przepływ-danych)
2. [Główne Skrypty Orkiestracji i Wykonania](#2-główne-skrypty-orkiestracji-i-wykonania)
   - [`run-main.sh`](#run-mainsh)
   - [`run-scenario.sh`](#run-scenariosh)
3. [Zarządzanie Bazą Danych i Danymi Testowymi](#3-zarządzanie-bazą-danych-i-danymi-testowymi)
   - [`db-setup.sh`](#db-setupsh)
   - [`db-reset.sh`](#db-resetsh)
   - [`jmeter-data.sh`](#jmeter-datash)
4. [Pakiet Analityczny i Wnioskowanie Statystyczne](#4-pakiet-analityczny-i-wnioskowanie-statystyczne)
   - [`summarize.py`](#summarizepy)
   - [Moduły pomocnicze (`summarize_common.py`, `summarize_data.py`, `summarize_stats.py`)](#moduły-pomocnicze-pakietu-analitycznego)
5. [Narzędzia Diagnostyczne i Badania Dymne (Smoke Tests)](#5-narzędzia-diagnostyczne-i-badania-dymne-smoke-tests)
   - [`golden-write-check.sh`](#golden-write-checksh)
   - [`sql-compare.sh`](#sql-comparesh)
   - [`query-count.sh`](#query-countsh)
6. [Zmienne Środowiskowe i Flagi Wykonawcze](#6-zmienne-środowiskowe-i-flagi-wykonawcze)
7. [Struktura Katalogu Wyników (`results/`) i Metadane](#7-struktura-katalogu-wyników-results-i-metadane)

---

## 1. Architektura Pipeline'u i Przepływ Danych

Pipeline eksperymentalny został zaprojektowany z myślą o pełnej deterministyczności, izolacji cgroups, eliminacji interferencji termicznych oraz braku dryftu stanu bazy danych pomiędzy powtórzeniami ($n = 10$).

```
┌────────────────────────────────────────────────────────────────────────┐
│                          INICJALIZACJA                                 │
│  db-setup.sh (migracje + seeding) ──> jmeter-data.sh (zakresy ID)      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                  ORKIESTRACJA: run-main.sh                             │
│       Pętla scenariuszy: S1 ──> S2 ──> S2-pool1 ──> S3                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│             SILNIK WYKONAWCZY: run-scenario.sh (n = 10)                │
│                                                                        │
│  Dla każdego powtórzenia (rep = 1..10):                                │
│    1. Losowanie kolejności frameworków (INTERLEAVE_SEED + rep)         │
│    2. db-reset.sh (przywrócenie czystej bazy + restart stosu)          │
│    3. Rozgrzewka (Warm-Up: 60 s / 120 s)                               │
│    4. Uruchomienie próbkowania docker stats -> stats.csv               │
│    5. Pomiar właściwy: JMeter CLI -> results.jtl                       │
│    6. Weryfikacja bramek integralności (Integrity Gates 1:1)           │
│    7. Zapis metadanych i sum kontrolnych -> meta.json                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                    ANALIZA: summarize.py                               │
│                                                                        │
│  - Obcięcie 10 s ramp-up                                               │
│  - Wyznaczenie percentyli ogona (p50, p95, p99 nearest-rank)           │
│  - Weryfikacja Low-Load Validity Rule (skalowanie >= 80%, CPU < 80%)   │
│  - Procedura Bootstrap (10 000 prób) dla H1 (Δp95), H2 (r), H3 (Dk)    │
│  - Generowanie raportów: runs.csv oraz summary.csv                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Główne Skrypty Orkiestracji i Wykonania

### [`run-main.sh`](file:///home/user/projekty/badanie/benchmark/scripts/run-main.sh)

Główny skrypt orkiestrujący pełny ciąg badawczy dla wszystkich zdefiniowanych scenariuszy ($n = 10$ niezależnych powtórzeń).

- **Ścieżka pliku:** [`benchmark/scripts/run-main.sh`](file:///home/user/projekty/badanie/benchmark/scripts/run-main.sh)
- **Składnia:**
  ```bash
  ./scripts/run-main.sh [s1 | s2 | s2-pool1 | s3 | all]
  ```
- **Domyślne działanie:** Bez podania argumentu uruchamia tryb `all`, wykonując sekwencyjnie wszystkie scenariusze wraz z automatycznym generowaniem podsumowań statystycznych:
  1. `run_s1`: Uruchamia [`run-scenario.sh both s1`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh) $\rightarrow$ wykonuje [`summarize.py s1`](file:///home/user/projekty/badanie/benchmark/scripts/summarize.py).
  2. `run_s2`: Uruchamia [`run-scenario.sh both s2`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh) $\rightarrow$ wykonuje [`summarize.py s2`](file:///home/user/projekty/badanie/benchmark/scripts/summarize.py).
  3. `run_s2_pool1`: Uruchamia NestJS z flagą `DB_POOL_SIZE=1` dla `s2` $\rightarrow$ wykonuje [`summarize.py s2-pool1`](file:///home/user/projekty/badanie/benchmark/scripts/summarize.py).
  4. `run_s3`: Uruchamia [`run-scenario.sh both s3`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh) $\rightarrow$ wykonuje [`summarize.py s3`](file:///home/user/projekty/badanie/benchmark/scripts/summarize.py).
- **Wznawialność (Resumable):** Skrypt można bezpiecznie przerwać kombinacją `Ctrl+C`. Ponowne wywołanie pomija już zrealizowane powtórzenia na podstawie plików [`meta.json`](#zawartość-pliku-metajson).

---

### [`run-scenario.sh`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh)

Niskopoziomowy silnik wykonawczy odpowiedzialny za realizację pojedynczego scenariusza pomiarowego w pełnej symetrii środowiskowej.

- **Ścieżka pliku:** [`benchmark/scripts/run-scenario.sh`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh)
- **Składnia:**
  ```bash
  # Uruchomienie obu frameworków z algorytmem przeplotu (zalecane)
  ./scripts/run-scenario.sh both <s1|s2|s3>

  # Uruchomienie pojedynczego frameworka
  ./scripts/run-scenario.sh <laravel|nestjs> <s1|s2|s3>
  ```

#### Kluczowe Funkcje i Mechanizmy:

1. **Izolacja Stosów Kontenerów ([`ensure_stack`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh#L81-L92)):**
   Dba o to, aby w danym momencie działał **wyłącznie jeden badany stos** aplikacji (`laravel` lub `nestjs`). Kontener drugiego frameworka oraz powiązany serwer proxy Nginx są zatrzymywane, co eliminuje rywalizację procesów o te same przypisane rdzenie CPU oraz pamięć RAM.

2. **Dostosowanie Puli Połączeń ([`align_nestjs_pool`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh#L94-L116)):**
   Weryfikuje i dynamicznie aktualizuje zmienną środowiskową `DB_POOL_SIZE` w kontenerze NestJS (np. zmiana z 10 na 1 dla scenariusza `s2-pool1`), po czym restartuje kontener i czeka na gotowość healthchecka.

3. **Algorytm Przeplotu ([`framework_order`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh#L187-L201)):**
   Kolejność uruchamiania frameworków (`laravel`, `nestjs`) w ramach każdego powtórzenia ($n=1..10$) jest pseudolosowo ustalana za pomocą ziarna `INTERLEAVE_SEED` (domyślnie `20261002`) oraz numeru powtórzenia. Zapobiega to faworyzowaniu technologii przez nagrzewanie procesora (*thermal throttling*) lub dryft tła systemu operacyjnego.

4. **Cykl Pojedynczego Przebiegu ([`run_one`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh#L203-L373)):**
   - Wywołanie [`scripts/db-reset.sh`](file:///home/user/projekty/badanie/benchmark/scripts/db-reset.sh) celem przywrócenia czystego stanu bazy danych.
   - **Faza Rozgrzewki (Warm-Up):** 60 s dla S1 i S3; 120 s dla S2 (próbki odrzucane z właściwych wyników).
   - **Próbkowanie Zasobów ([`start_stats`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh#L134-L157)):** W tle uruchamiany jest proces próbkujący `docker stats` (CPU%, RAM) do pliku `stats.csv` z częstotliwością $\sim 0.5$ s.
   - **Faza Pomiarowa (Measurement Window):** 60 s dla S1 i S3; 120 s dla S2. Pierwsze 10 s (ramp-up) jest automatycznie odrzucane w analizie.
   - Zatrzymanie zbierania statystyk ([`stop_stats`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh#L159-L163)) i walidacja bramek integralności.

5. **Bramki Integralności Danych (Integrity Gates):**
   - Dla endpointów odczytu weryfikuje niezmienniczość liczby wierszy w tabelach.
   - Dla tworzenia zamówień (EP7) weryfikuje dokładny stosunek 1:1 liczby wstawionych wierszy w tabelach `orders` i `order_items` do liczby pomyślnych odpowiedzi HTTP 201. W przypadku jakiejkolwiek niespójności bieg jest natychmiast unieważniany.

---

## 3. Zarządzanie Bazą Danych i Danymi Testowymi

### [`db-setup.sh`](file:///home/user/projekty/badanie/benchmark/scripts/db-setup.sh)

Jednorazowy skrypt inicjalizacyjny schematów i deterministycznych danych testowych.

- **Ścieżka pliku:** [`benchmark/scripts/db-setup.sh`](file:///home/user/projekty/badanie/benchmark/scripts/db-setup.sh)
- **Składnia:**
  ```bash
  ./scripts/db-setup.sh
  ```
- **Procedura działania:**
  1. Sprawdza obecność i czeka na gotowość serwera PostgreSQL 16.
  2. Wywołuje w kontenerze `laravel-tools` polecenie `php artisan migrate:fresh --seed --force` na bazie `laravel_app` (seeder używa ustalonego ziarna `mt_srand(20260101)`).
  3. Klonuje bazę `laravel_app` do bazy `nestjs_app` instrukcją PostgreSQL: `CREATE DATABASE nestjs_app TEMPLATE laravel_app`.
  4. Tworzy niezmienne szablony wzorcowe: `laravel_app_template` oraz `nestjs_app_template`.

---

### [`db-reset.sh`](file:///home/user/projekty/badanie/benchmark/scripts/db-reset.sh)

Skrypt błyskawicznego przywracania stanu baz danych z szablonów wzorcowych.

- **Ścieżka pliku:** [`benchmark/scripts/db-reset.sh`](file:///home/user/projekty/badanie/benchmark/scripts/db-reset.sh)
- **Składnia:**
  ```bash
  ./scripts/db-reset.sh [laravel | nestjs | both]   # domyślnie: both
  ```
- **Procedura działania:**
  1. Zabija aktywne połączenia do baz roboczych za pomocą `pg_terminate_backend`.
  2. W ułamku sekundy odtwarza bazę z szablonu template (`DROP DATABASE ...; CREATE DATABASE ... TEMPLATE ..._template`).
  3. Restartuje kontenery aplikacji i Nginx, oczekując na pomyślny wynik healthchecka. Resetuje to stany w pamięci (JIT TurboFan w V8, pamięć współdzieloną OPcache, pule połączeń TypeORM/PDO).

---

### [`jmeter-data.sh`](file:///home/user/projekty/badanie/benchmark/scripts/jmeter-data.sh)

Eksport deterministycznych parametrów zapytaniowych dla planów testowych Apache JMeter.

- **Ścieżka pliku:** [`benchmark/scripts/jmeter-data.sh`](file:///home/user/projekty/badanie/benchmark/scripts/jmeter-data.sh)
- **Składnia:**
  ```bash
  ./scripts/jmeter-data.sh
  ```
- **Generowane artefakty (w `jmeter/data/`):**
  - `ranges.properties`: Zakresy kluczy głównych (`orders.max`, `dishes.max`, `tables.max`) oraz liczby stron dla zapytań losowych, co całkowicie zapobiega występowaniu pozornych błędów HTTP 404 w testach obciążeniowych.
  - `available_menu_items.csv`: Lista identyfikatorów dań spełniających warunek `is_available = true` (wykorzystywana w payloadzie EP7 przy tworzeniu zamówień).

---

## 4. Pakiet Analityczny i Wnioskowanie Statystyczne

### [`summarize.py`](file:///home/user/projekty/badanie/benchmark/scripts/summarize.py)

Główny moduł analityczny przetwarzający surowe logi JMeter (`results.jtl`) oraz logi telemetryczne (`stats.csv`) do postaci tabel wynikowych oraz werdyktów hipotez badawczych.

- **Ścieżka pliku:** [`benchmark/scripts/summarize.py`](file:///home/user/projekty/badanie/benchmark/scripts/summarize.py)
- **Składnia:**
  ```bash
  python3 scripts/summarize.py <s1 | s2 | s2-pool1 | s3>
  ```
- **Wyjściowe pliki tabelaryczne:**
  - `results/<scenario>/runs.csv`: Dane ze wszystkich powtórzeń ($n=10$) dla każdego endpointu i poziomu obciążenia VU.
  - `results/<scenario>/summary.csv`: Mediany oraz odchylenia standardowe (IQR / std) zagregowane po serii pomiarowej.

#### Rygory Metodyczne i Statystyczne:

1. **Okno Stanu Ustalonego (*Steady-State*):**
   Próbki z pierwszych 10 s (ramp-up) są ignorowane. Okno obejmuje żądania, które rozpoczęły się między `rampup_s` a `duration_s`.
2. **Kwantyle Ogonowe:**
   Wyznaczanie $p_{50}$, $p_{95}$ i $p_{99}$ metodą najbliższej rangi (*nearest-rank method*) na poziomie pojedynczych próbek.
3. **Reguła Poprawności Niskiego Obciążenia (*Low-Load Validity Rule*):**
   Weryfikuje warunek niskiego obciążenia: współczynnik skalowania przepustowości $X(N)/(N \cdot X(1)) \ge 0.80$ oraz obciążenie CPU kontenerów aplikacji i bazy danych poniżej $80\%$ (320% w jednostkach docker stats).
4. **Weryfikacja Hipotez (Procedura Bootstrap 10 000 prób):**
   - **H1 (S1):** 95% przedział ufności bootstrap dla względnej różnicy $|\Delta p_{95}| \le 15\%$ przy odsetku błędów $< 1\%$.
   - **H2 (S2):** 95% przedział ufności dla ilorazu nachyleń regresji OLS $r = s_L / s_N > 1$ na EP3.
   - **H3 (S3):** 95% przedział ufności dla kontrastu Difference-in-Differences $D_k = S_k - S_{\text{EP1}} > 2\text{ ms}$ na EP2 przy 2 VU.
5. **Metryki Wtórne i Diagnostyczne:**
   - Estymacja ciągła opóźnienia Prawem Little’a: $R \approx N / X$ (omijająca 1-ms kwantowanie JMetera).
   - Zużycie czasu procesora na pojedyncze obsłużone żądanie (*CPU time per request*).

---

### Moduły Pomocnicze Pakietu Analitycznego

- **[`summarize_common.py`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_common.py):**
  - Definicje stałych progowych ([`H1_LIMIT_PCT = 15.0`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_common.py#L9), [`H3_THRESHOLD_MS = 2.0`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_common.py#L24), [`LOWLOAD_SCALING_MIN = 0.80`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_common.py#L19)).
  - Parametry procedury bootstrap ([`BOOTSTRAP_SEED = 20261002`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_common.py#L23), [`BOOTSTRAP_N = 10_000`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_common.py#L22)).
  - Klasa pomocnicza [`FrameworkPair`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_common.py#L64-L113) ułatwiająca symetryczne zestawianie metryk obu frameworków.
  - Funkcje obliczające luki opóźnień ([`signed_gap`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_common.py#L49-L50)) oraz kontrast wrażliwości ([`d_k`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_common.py#L52-L53)).

- **[`summarize_data.py`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_data.py):**
  - Logika parsowania surowych plików CSV z logów JMetera ([`results.jtl`](#7-struktura-katalogu-wyników-results-i-metadane)) oraz logów telemetrycznych Docker (`stats.csv`).
  - Filtrowanie okna pomiarowego (obcinanie próbek z fazy rozruchu ramp-up).
  - Standaryzacja i konwersja jednostek pamięci (B, KiB, MiB, GiB) na megabajty binarne.

- **[`summarize_stats.py`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_stats.py):**
  - Funkcja percentyli ogona metodą nearest-rank ([`percentile`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_stats.py#L10-L12)).
  - Implementacja estymatora bootstrap dla względnej różnicy median ([`bootstrap_rel_delta`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_stats.py#L27-L35)).
  - Implementacja bootstrapu dla kontrastu Difference-in-Differences ([`bootstrap_d_k`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_stats.py#L37-L57)).
  - Obliczanie nachylenia prostej regresji liniowej OLS ([`slope`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_stats.py#L59-L74)) oraz estymator bootstrap ilorazu nachyleń ([`bootstrap_slope_ratio`](file:///home/user/projekty/badanie/benchmark/scripts/summarize_stats.py#L76-L92)).

---

## 5. Narzędzia Diagnostyczne i Badania Dymne (Smoke Tests)

### [`golden-write-check.sh`](file:///home/user/projekty/badanie/benchmark/scripts/golden-write-check.sh)

Weryfikacja determinizmu operacji modyfikacji danych (mutacji bazy) oraz ścisłej spójności encji w obu frameworkach.

- **Ścieżka pliku:** [`benchmark/scripts/golden-write-check.sh`](file:///home/user/projekty/badanie/benchmark/scripts/golden-write-check.sh)
- **Składnia:**
  ```bash
  ./scripts/golden-write-check.sh <laravel | nestjs>
  ```
- **Działanie:**
  - Wysyła deterministyczne żądania HTTP dla endpointów mutujących (EP7, EP8, EP9).
  - Wykonuje zrzut wstawionych i zaktualizowanych rekordów bezpośrednio z bazy danych w formacie JSON (z pominięciem generowanych kluczy i znaczników czasu `created_at`/`updated_at`).
  - Pozwala na bezpośrednie porównanie zgodności struktur danych obu frameworków standardowym poleceniem `diff`.

---

### [`sql-compare.sh`](file:///home/user/projekty/badanie/benchmark/scripts/sql-compare.sh)

Porównanie zapytań SQL generowanych przez Eloquent (Laravel) i TypeORM (NestJS).

- **Ścieżka pliku:** [`benchmark/scripts/sql-compare.sh`](file:///home/user/projekty/badanie/benchmark/scripts/sql-compare.sh)
- **Składnia:**
  ```bash
  ./scripts/sql-compare.sh <laravel | nestjs> [liczba_powtórzeń]
  ```
- **Działanie:**
  - Odpytuje wszystkie endpointy z włączonym nagłówkiem `X-Debug-Queries: 1`.
  - Agreguje statystyki z modułu `pg_stat_statements` (liczba wywołań, całkowity czas wykonania, średni czas na zapytanie).
  - Generuje raport diagnostyczny do pliku `results/smoke/sql-compare-<framework>.txt`.

---

### [`query-count.sh`](file:///home/user/projekty/badanie/benchmark/scripts/query-count.sh)

Diagnostyka liczby zapytań SQL generowanych przez poszczególne endpointy scenariusza S3 pod kątem problemu N+1.

- **Ścieżka pliku:** [`benchmark/scripts/query-count.sh`](file:///home/user/projekty/badanie/benchmark/scripts/query-count.sh)
- **Składnia:**
  ```bash
  ./scripts/query-count.sh <laravel | nestjs>
  ```
- **Działanie:**
  - Wysyła żądania do endpointów scenariusza S3 z nagłówkiem `X-Debug-Queries: 1`.
  - Odczytuje dokładną liczbę zapytań zwróconą w nagłówku odpowiedzi `X-Query-Count`.
  - Zapisuje zestawienie do pliku `results/s3/query-count-<framework>.txt`, weryfikując pełną symetrię złożoności zapytaniowej obu ORM-ów.

---

## 6. Zmienne Środowiskowe i Flagi Wykonawcze

Działanie skryptu [`run-scenario.sh`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh) można konfigurować za pomocą zmiennych środowiskowych:

| Zmienna | Domyślna wartość | Opis |
| :--- | :--- | :--- |
| `ENDPOINTS` | Domyślne dla scenariusza | Lista endpointów objętych badaniem (np. `ENDPOINTS="EP1 EP8"`) |
| `USERS` | Domyślne dla scenariusza | Poziomy współbieżności wirtualnych użytkowników VU (np. `USERS="1 2"`) |
| `REPS` | `10` | Liczba niezależnych powtórzeń pomiarowych |
| `WARMUP` | `60` (S1/S3), `120` (S2) | Czas trwania rozgrzewki w sekundach |
| `DURATION` | `60` (S1/S3), `120` (S2) | Czas trwania właściwego okna pomiarowego w sekundach |
| `RAMPUP` | `10` | Czas rozruchu wątków w JMeterze (odrzucany z analizy) |
| `INTERLEAVE_SEED` | `20261002` | Ziarno generatora pseudolosowego przeplotu kolejności frameworków |
| `DB_POOL_SIZE` | `10` | Rozmiar puli połączeń NestJS (nadpisanie na `1` dla serii kontrolnej `s2-pool1`) |
| `OUT_NAME` | Wartość `$scenario` | Nazwa katalogu docelowego w katalogu `results/` |

---

## 7. Struktura Katalogu Wyników (`results/`) i Metadane

Wyniki każdego pojedynczego biegu pomiarowego zapisywane są w ściśle ustrukturyzowanej hierarchii katalogów:

```
results/
├── s1/
│   ├── laravel/
│   │   └── EP1/
│   │       ├── vu1/
│   │       │   ├── rep01/
│   │       │   │   ├── results.jtl     # Surowy ślad próbek JMetera (format CSV)
│   │       │   │   ├── stats.csv       # Telemetria docker stats (CPU%, RAM MiB)
│   │       │   │   ├── warmup.log      # Log wykonania rozgrzewki
│   │       │   │   ├── jmeter.log      # Log silnika JMeter
│   │       │   │   └── meta.json       # Metadane środowiska i sumy kontrolne
│   │       │   ├── ...
│   │       │   └── rep10/
│   │       └── vu2/ ...
│   ├── nestjs/ ...
│   ├── runs.csv                        # Zbiorcza tabela wszystkich powtórzeń
│   └── summary.csv                     # Zagregowane mediany i odchylenia
├── s2/ ...
├── s2-pool1/ ...
└── s3/ ...
```

### Zawartość pliku `meta.json`

Plik `meta.json` generowany jest po każdym udanym przebiegu i zawiera metadane gwarantujące powtarzalność oraz wznawialność:

```json
{
  "scenario": "s1",
  "framework": "laravel",
  "endpoint": "EP1",
  "users": 1,
  "rep": "rep01",
  "status": "complete",
  "start_epoch": 1776000000,
  "end_epoch": 1776000060,
  "git_commit": "abcdef123456...",
  "git_dirty": false,
  "laravel_app_tree": "9f83a4b...",
  "nestjs_app_tree": "1c72e3a...",
  "cgroups": {
    "cpu_quota": 400000,
    "cpu_period": 100000,
    "memory_limit": 4294967296
  },
  "row_counts_before": { "orders": 10000, "order_items": 30000 },
  "row_counts_after": { "orders": 10000, "order_items": 30000 }
}
```

Plik ten umożliwia skryptowi [`run-scenario.sh`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh) bezpieczne wznawianie przerwanych serii oraz natychmiastowe wykrywanie jakichkolwiek modyfikacji kodu źródłowego lub limitów zasobów pomiędzy powtórzeniami.
