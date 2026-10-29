# Dokumentacja Skryptów i Pipeline'u Pomiarowego

Kompleksowa dokumentacja techniczna narzędzi automatyzacji, orkiestracji eksperymentów, zbierania metryk telemetrycznych, analizy wrażliwości oraz wnioskowania statystycznego i wizualizacji w projekcie empirycznego porównania wydajności frameworków **Laravel 13 (PHP 8.4)** i **NestJS 11 (Node.js 24 LTS)**.

Wszystkie skrypty znajdują się w katalogu [`benchmark/scripts/`](file:///home/wojtek/projekty/badanie/benchmark/scripts/) i są przystosowane do uruchamiania w środowisku Linux oraz WSL2 (Ubuntu 22.04+).

---

## Spis Treści

1. [Architektura Pipeline'u i Przepływ Danych](#1-architektura-pipelineu-i-przepływ-danych)
2. [Główne Skrypty Orkiestracji i Wykonania](#2-główne-skrypty-orkiestracji-i-wykonania)
   - [`run-main.sh`](#run-mainsh)
   - [`run-scenario.sh`](#run-scenariosh)
   - [`run-s2-sensitivity.sh`](#run-s2-sensitivitysh)
   - [`run-fpm-pilot.py`](#run-fpm-pilotpy)
3. [Zarządzanie Bazą Danych i Danymi Testowymi](#3-zarządzanie-bazą-danych-i-danymi-testowymi)
   - [`db-setup.sh`](#db-setupsh)
   - [`db-reset.sh`](#db-resetsh)
   - [`jmeter-data.sh`](#jmeter-datash)
4. [Pakiet Analityczny, Wnioskowanie Statystyczne i Wizualizacja](#4-pakiet-analityczny-wnioskowanie-statystyczne-i-wizualizacja)
   - [`summarize.py`](#summarizepy)
   - [Moduły pomocnicze (`summarize_common.py`, `summarize_data.py`, `summarize_stats.py`)](#moduły-pomocnicze-pakietu-analitycznego)
   - [Skrypty generowania wykresów (`plot_s1.py`, `plot_s2.py`, `plot_s3.py`)](#skrypty-generowania-wykresów-plot_s1py-plot_s2py-plot_s3py)
5. [Narzędzia Diagnostyczne i Profilowanie SQL](#5-narzędzia-diagnostyczne-i-profilowanie-sql)
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
│        ORKIESTRACJA: run-main.sh / run-s2-sensitivity.sh               │
│   Scenariusze: S1 ──> S2 ──> S2-pool1 / S2-fpm8 ──> S3                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│             SILNIK WYKONAWCZY: run-scenario.sh (n = 10)                │
│                                                                        │
│  Dla każdego powtórzenia (rep = 1..10):                                │
│    1. Losowanie kolejności frameworków (INTERLEAVE_SEED + rep)         │
│    2. db-reset.sh (przywrócenie czystej bazy + restart stosu)          │
│    3. Wyrównanie DB_POOL_SIZE (NestJS) i PM_MAX_CHILDREN (Laravel)     │
│    4. Rozgrzewka (Warm-Up: 60 s dla S1/S3; 120 s dla S2)               │
│    5. Uruchomienie próbkowania docker stats -> stats.csv               │
│    6. Pomiar właściwy: JMeter CLI -> results.jtl                       │
│    7. Weryfikacja bramek integralności (Integrity Gates 1:1)           │
│    8. Zapis metadanych i sum kontrolnych -> meta.json                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│         ANALIZA I WIZUALIZACJA: summarize.py + plot_s*.py              │
│                                                                        │
│  - Obcięcie 10 s ramp-up (badanie okna steady-state)                   │
│  - Wyznaczenie percentyli ogona (p50, p95, p99 nearest-rank)           │
│  - Weryfikacja Low-Load Validity Rule (skalowanie >= 80%, CPU < 80%)   │
│  - Procedura Bootstrap (10 000 prób) dla H1 (Δp95), H2 (r), H3 (Dk)    │
│  - Generowanie raportów: runs.csv, summary.csv oraz wykresów PNG       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Główne Skrypty Orkiestracji i Wykonania

### [`run-main.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-main.sh)

Główny skrypt orkiestrujący pełny ciąg badawczy dla wszystkich zdefiniowanych scenariuszy serii głównej ($n = 10$ niezależnych powtórzeń).

- **Ścieżka pliku:** [`benchmark/scripts/run-main.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-main.sh)
- **Składnia:**
  ```bash
  ./scripts/run-main.sh [s1 | s2 | s2-pool1 | s3 | all]
  ```
- **Domyślne działanie:** Bez podania argumentu uruchamia tryb `all`, wykonując sekwencyjnie wszystkie scenariusze wraz z automatycznym generowaniem podsumowań statystycznych:
  1. `run_s1`: Uruchamia [`run-scenario.sh both s1`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh) $\rightarrow$ wykonuje [`summarize.py s1`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize.py).
  2. `run_s2`: Uruchamia [`run-scenario.sh both s2`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh) $\rightarrow$ wykonuje [`summarize.py s2`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize.py).
  3. `run_s2_pool1`: Uruchamia NestJS z flagą `DB_POOL_SIZE=1` dla `s2` $\rightarrow$ wykonuje [`summarize.py s2-pool1`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize.py).
  4. `run_s3`: Uruchamia [`run-scenario.sh both s3`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh) $\rightarrow$ wykonuje [`summarize.py s3`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize.py).
- **Wznawialność (Resumable):** Skrypt można bezpiecznie przerwać kombinacją `Ctrl+C`. Ponowne wywołanie pomija już zrealizowane powtórzenia na podstawie plików [`meta.json`](#zawartość-pliku-metajson).

---

### [`run-scenario.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh)

Niskopoziomowy silnik wykonawczy odpowiedzialny za realizację pojedynczego scenariusza pomiarowego w pełnej symetrii środowiskowej.

- **Ścieżka pliku:** [`benchmark/scripts/run-scenario.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh)
- **Składnia:**
  ```bash
  # Uruchomienie obu frameworków z algorytmem przeplotu (zalecane)
  ./scripts/run-scenario.sh both <s1|s2|s3>

  # Uruchomienie pojedynczego frameworka
  ./scripts/run-scenario.sh <laravel|nestjs> <s1|s2|s3>
  ```
- **Domyślne zakresy scenariuszy:**
  - `s1`: `ENDPOINTS="EP1 EP5"`, `USERS="1 2 4 10"`, `WARMUP=60`, `DURATION=60` (dodatkowo obsługiwane: `EP2`, `PING`).
  - `s2`: `ENDPOINTS="EP3 EP7"`, `USERS="200 500 1000"`, `WARMUP=120`, `DURATION=120`.
  - `s3`: `ENDPOINTS="EP1 EP2 EP2b EP4 EP6"`, `USERS="1 2 4 10"`, `WARMUP=60`, `DURATION=60` (dodatkowo obsługiwane: `EP8`).

#### Kluczowe Funkcje i Mechanizmy:

1. **Izolacja Stosów Kontenerów ([`ensure_stack`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh#L81-L92)):**
   Dba o to, aby w danym momencie działał **wyłącznie jeden badany stos** aplikacji (`laravel` lub `nestjs`). Kontener drugiego frameworka oraz powiązany serwer proxy Nginx są zatrzymywane, co eliminuje rywalizację procesów o rdzenie CPU i pamięć RAM.

2. **Dynamiczne Dostosowanie Puli Połączeń i Workerów ([`align_nestjs_pool`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh#L94-L108) oraz [`align_laravel_workers`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh#L110-L126)):**
   Weryfikuje i dynamicznie aktualizuje zmienną `DB_POOL_SIZE` w kontenerze NestJS (domyślnie `10`, w kontroli wrażliwości `1` $\rightarrow$ katalog `results/s2-pool1/`) oraz zmienną `PM_MAX_CHILDREN` w kontenerze Laravel (domyślnie `4`, w kontroli wrażliwości `8` $\rightarrow$ katalog `results/s2-fpm8/`), odtwarzając kontener w razie rozbieżności.

3. **Algorytm Przeplotu ([`framework_order`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh#L204-L218)):**
   Kolejność uruchamiania frameworków (`laravel`, `nestjs`) w ramach każdego powtórzenia ($n=1..10$) jest pseudolosowo ustalana za pomocą ziarna `INTERLEAVE_SEED` (domyślnie `20261002`) oraz numeru powtórzenia. Zapobiega to faworyzowaniu technologii przez nagrzewanie procesora (*thermal throttling*) lub dryft tła systemu operacyjnego.

4. **Cykl Pojedynczego Przebiegu ([`run_one`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh#L220-L390)):**
   - Wywołanie [`scripts/db-reset.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/db-reset.sh) celem przywrócenia czystego stanu bazy danych.
   - **Faza Rozgrzewki (Warm-Up):** 60 s dla S1 i S3; 120 s dla S2 (próbki odrzucane z właściwych wyników).
   - **Próbkowanie Zasobów (`start_stats`):** W tle uruchamiany jest proces próbkujący `docker stats` (CPU%, RAM) do pliku `stats.csv` z częstotliwością $\sim 0.5$ s.
   - **Faza Pomiarowa (Measurement Window):** 60 s dla S1 i S3; 120 s dla S2. Pierwsze 10 s (ramp-up) jest automatycznie odrzucane w analizie, co daje 50 s lub 110 s czystego okna stanu ustalonego (*steady-state*).
   - Zatrzymanie zbierania statystyk i walidacja bramek integralności.

5. **Bramki Integralności Danych (Integrity Gates):**
   - Dla endpointów odczytu i aktualizacji `in-place` (`EP5`) weryfikuje niezmienniczość liczby wierszy w tabelach (`orders = 100 000`, `order_items = 299 695`, `reservations = 100 000`).
   - Dla tworzenia zamówień (`EP7`) weryfikuje dokładny stosunek 1:1 liczby nowych wierszy w tabelach `orders` i `order_items` do liczby pomyślnych odpowiedzi HTTP 201 (zarówno z rozgrzewki, jak i pomiaru). W przypadku jakiejkolwiek niespójności bieg jest natychmiast oznaczany jako nieudany.

---

### [`run-s2-sensitivity.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-s2-sensitivity.sh)

Skrypt wykonujący symetryczną serię kontroli wrażliwości ($n = 10$) w Scenariuszu S2 na zasobożernym endpointcie odczytowym `EP3` (200, 500, 1000 VU):
1. **NestJS z `DB_POOL_SIZE=1`** (4 połączenia bazodanowe łącznie w 4 instancjach PM2, zrównane z domyślnymi 4 połączeniami Laravela) $\rightarrow$ zapis do `results/s2-pool1/`.
2. **Laravel z `PM_MAX_CHILDREN=8`** (8 procesów roboczych PHP-FPM, wyznaczony w pilotażu punkt optymalnego nasycenia $2 \times \text{vCPU}$) $\rightarrow$ zapis do `results/s2-fpm8/`.
3. Automatyczne podsumowanie statystyczne obu serii oraz regeneracja wykresu publikacyjnego `fig2_s2_scalability_pool.png`.

---

### [`run-fpm-pilot.py`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-fpm-pilot.py)

Skrypt eksploracyjny w języku Python służący do wyznaczenia pełnej krzywej skalowalności procesów roboczych PHP-FPM w Laravelu (zgodnie z modelem *Universal Scalability Law*).
- Wykonuje automatycznie 24 przebiegi pomiarowe dla siatki `PM_MAX_CHILDREN` $\in \{4, 8, 16, 24, 32, 40\}$ na endpointach `EP3` (odczyt) oraz `EP7` (zapis transakcyjny) przy współbieżności 500 i 1000 VU.
- Zapisuje zagregowaną tabelę wyników do `results/smoke/s2-fpm-pilot/summary.csv` (szczegółowa analiza wyników znajduje się w Sekcji 3.1 pliku [`results.md`](file:///home/wojtek/projekty/badanie/results.md)).

---

## 3. Zarządzanie Bazą Danych i Danymi Testowymi

### [`db-setup.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/db-setup.sh)

Jednorazowy skrypt inicjalizacyjny schematów i deterministycznych danych testowych.

- **Ścieżka pliku:** [`benchmark/scripts/db-setup.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/db-setup.sh)
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

### [`db-reset.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/db-reset.sh)

Skrypt błyskawicznego przywracania stanu baz danych z szablonów wzorcowych.

- **Ścieżka pliku:** [`benchmark/scripts/db-reset.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/db-reset.sh)
- **Składnia:**
  ```bash
  ./scripts/db-reset.sh [laravel | nestjs | both]   # domyślnie: both
  ```
- **Procedura działania:**
  1. Zamyka aktywne połączenia do baz roboczych za pomocą `pg_terminate_backend`.
  2. W kilka sekund odtwarza bazę z szablonu (`DROP DATABASE ...; CREATE DATABASE ... TEMPLATE ..._template`).
  3. Restartuje kontenery aplikacji i Nginx, oczekując na pomyślny wynik healthchecka. Resetuje to stany w pamięci (JIT TurboFan w V8, pamięć współdzieloną OPcache, pule połączeń TypeORM/PDO).

---

### [`jmeter-data.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/jmeter-data.sh)

Eksport deterministycznych parametrów zapytaniowych dla planów testowych Apache JMeter.

- **Ścieżka pliku:** [`benchmark/scripts/jmeter-data.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/jmeter-data.sh)
- **Składnia:**
  ```bash
  ./scripts/jmeter-data.sh
  ```
- **Generowane artefakty (w `benchmark/jmeter/data/`):**
  - `ranges.properties`: Zakresy kluczy głównych (`orders.max=100000`, `dishes.max=500`, `tables.max=200`) oraz liczby stron (`ep1.pages=10`, `ep2.pages=23`, `ep3.pages=5000`), co całkowicie zapobiega występowaniu pozornych błędów HTTP 404 w testach obciążeniowych.
  - `available_menu_items.csv`: Lista 445 identyfikatorów pozycji menu spełniających warunek `is_available = true` (wykorzystywana w payloadzie `EP7`).

---

## 4. Pakiet Analityczny, Wnioskowanie Statystyczne i Wizualizacja

### [`summarize.py`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize.py)

Główny moduł analityczny przetwarzający surowe logi JMeter (`results.jtl`) oraz logi telemetryczne (`stats.csv`) do postaci tabel wynikowych oraz formalnych werdyktów hipotez badawczych H1–H3.

- **Ścieżka pliku:** [`benchmark/scripts/summarize.py`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize.py)
- **Składnia:**
  ```bash
  python3 scripts/summarize.py <s1 | s2 | s2-pool1 | s2-fpm8 | s3>
  ```
- **Wyjściowe pliki tabelaryczne:**
  - `results/<scenario>/runs.csv`: Dane ze wszystkich powtórzeń ($n=10$) dla każdego endpointu i poziomu obciążenia VU.
  - `results/<scenario>/summary.csv`: Mediany oraz odchylenia standardowe zagregowane po serii pomiarowej.

#### Rygory Metodyczne i Statystyczne:

1. **Okno Stanu Ustalonego (*Steady-State*):**
   Próbki z pierwszych 10 s (`rampup_s`) są ignorowane. Okno obejmuje żądania, które rozpoczęły się między `rampup_s` a `duration_s`.
2. **Kwantyle Ogonowe:**
   Wyznaczanie $p_{50}$, $p_{95}$ i $p_{99}$ metodą najbliższej rangi (*nearest-rank method*) na poziomie pojedynczych próbek.
3. **Reguła Poprawności Niskiego Obciążenia (*Low-Load Validity Rule*):**
   Weryfikuje warunek niskiego obciążenia: współczynnik skalowania przepustowości $X(N)/(N \cdot X(1)) \ge 0.80$ oraz obciążenie CPU kontenerów aplikacji i bazy danych poniżej $80\%$ limitu ($< 320\%$ w jednostkach `docker stats`). Wyznacza najdłuższy prefiks z listy `{1, 2, 4, 10}` spełniający kryteria (w serii głównej: `{1, 2}` VU).
4. **Weryfikacja Hipotez (Procedura Bootstrap 10 000 prób, `BOOTSTRAP_SEED = 20261002`):**
   - **H1 (S1 – `EP1`, `EP5`):** 95% przedział ufności bootstrap dla względnej różnicy $\Delta p_{95} = \frac{|p_{95,L} - p_{95,N}|}{(p_{95,L} + p_{95,N})/2} \times 100\% \le 15\%$ przy odsetku błędów $< 1\%$.
   - **H2 (S2 – `EP3` oraz pomocniczo `EP7`):** 95% przedział ufności dla ilorazu nachyleń regresji liniowej OLS $r = s_L / s_N > 1$ dla $N \in \{200, 500, 1000\}$ VU.
   - **H3 (S3 – główny cel `EP2`, obserwacje `EP4`, `EP6` względem punktu odniesienia `EP2b`):** 95% przedział ufności dla kontrastu Difference-in-Differences $D_k = (p_{95,L}(k) - p_{95,N}(k)) - (p_{95,L}(\text{EP2b}) - p_{95,N}(\text{EP2b}))$ z trójwartościową regułą decyzyjną przy 2 VU (*supported* gdy dolna granica CI $> 2.0\text{ ms}$ i $D > 0$ przy 1 VU; *rejected* gdy górna granica CI $\le 0\text{ ms}$; *inconclusive* w przeciwnym razie).
5. **Metryki Wtórne i Diagnostyczne:**
   - Estymacja ciągła opóźnienia Prawem Little’a: $R \approx N / X$ (omijająca 1-ms kwantowanie JMetera).
   - Znormalizowany jednordzeniowy czas CPU na pojedyncze obsłużone żądanie (*CPU time per request*).

---

### Moduły Pomocnicze Pakietu Analitycznego

- **[`summarize_common.py`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize_common.py):**
  - Definicje stałych progowych: `H1_LIMIT_PCT = 15.0`, `H1_ENDPOINTS = ("EP1", "EP5")`, `H3_PRIMARY_ENDPOINT = "EP2"`, `H3_DEFAULT_REFERENCE = "EP2b"`, `H3_THRESHOLD_MS = 2.0`, `LOWLOAD_SCALING_MIN = 0.80`, `LOWLOAD_CPU_SHARE_MAX = 0.80`.
  - Parametry procedury bootstrap: `BOOTSTRAP_SEED = 20261002`, `BOOTSTRAP_N = 10_000`.
  - Klasa [`FrameworkPair`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize_common.py#L67-L82) oraz funkcje obliczające luki opóźnień (`signed_gap`) i kontrasty Difference-in-Differences (`d_k`, `metric_contrast`).

- **[`summarize_data.py`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize_data.py):**
  - Logika parsowania surowych plików CSV z logów JMetera (`results.jtl`) oraz logów telemetrycznych Docker (`stats.csv`).
  - Filtrowanie okna pomiarowego (obcinanie próbek z fazy rozruchu ramp-up).
  - Standaryzacja i konwersja jednostek pamięci (B, KiB, MiB, GiB) na megabajty binarne (MiB).

- **[`summarize_stats.py`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize_stats.py):**
  - Funkcja percentyli ogona metodą nearest-rank (`percentile`).
  - Implementacje estymatorów bootstrap dla względnej różnicy median (`bootstrap_rel_delta`), kontrastu Difference-in-Differences (`bootstrap_d_k`) oraz ilorazu nachyleń OLS (`bootstrap_slope_ratio`).

---

### Skrypty Generowania Wykresów (`plot_s1.py`, `plot_s2.py`, `plot_s3.py`)

Skrypty wizualizacyjne generujące wykresy publikacyjne (300 DPI) bezpośrednio z plików `summary.csv` i `runs.csv` do katalogu `dokumenty/figures/`:
- **[`plot_s1.py`](file:///home/wojtek/projekty/badanie/benchmark/scripts/plot_s1.py):** Generuje wykresy bazowej wydajności S1 (opóźnienia $p_{95}$, przepustowość, zużycie CPU/req i profil pamięci RAM dla `EP1` i `EP5`).
- **[`plot_s2.py`](file:///home/wojtek/projekty/badanie/benchmark/scripts/plot_s2.py):** Generuje dwupanelowy wykres `dokumenty/figures/fig2_s2_scalability_pool.png`:
  - Panel (a): Skalowanie opóźnień $p_{95}$ w funkcji współbieżności (200, 500, 1000 VU) z prostymi regresji OLS dla `EP3` i `EP7`.
  - Panel (b): Kontrola wrażliwości puli połączeń i workerów na `EP3` (porównanie domyślnego NestJS [40 conn], NestJS `DB_POOL_SIZE=1` [4 conn], domyślnego Laravela [4 workery] oraz Laravela z 8 i 40 workerami).
- **[`plot_s3.py`](file:///home/wojtek/projekty/badanie/benchmark/scripts/plot_s3.py):** Generuje dwupanelowy wykres `dokumenty/figures/fig3_s3_relational_convergence.png`:
  - Panel (a): Kontrasty Difference-in-Differences $D_k$ względem `EP2b` wraz z 95% przedziałami ufności bootstrap i progiem decyzyjnym $2.0\text{ ms}$.
  - Panel (b): Zbieżność czasów odpowiedzi obu frameworków na zasobożernej agregacji bazodanowej `EP6`.

---

## 5. Narzędzia Diagnostyczne i Profilowanie SQL

### [`golden-write-check.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/golden-write-check.sh)

Weryfikacja determinizmu operacji modyfikacji danych (mutacji bazy) oraz ścisłej spójności encji w obu frameworkach.

- **Ścieżka pliku:** [`benchmark/scripts/golden-write-check.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/golden-write-check.sh)
- **Składnia:**
  ```bash
  ./scripts/golden-write-check.sh <laravel | nestjs>
  ```
- **Działanie:**
  - Wysyła deterministyczne żądania HTTP dla wszystkich trzech endpointów mutujących: `EP7` (`POST /api/orders`), `EP5` (`PATCH /api/orders/1/status`) oraz `EP9` (`POST /api/reservations`).
  - Wykonuje zrzut wstawionych i zaktualizowanych rekordów bezpośrednio z bazy danych w formacie JSON (z pominięciem generowanych kluczy i znaczników czasu `created_at`/`updated_at`), co pozwala na weryfikację zgodności 1:1 poleceniem `diff`.

---

### [`sql-compare.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/sql-compare.sh)

Profilowanie zapytań SQL generowanych przez Eloquent (Laravel) i TypeORM (NestJS) przy użyciu rozszerzenia serwerowego `pg_stat_statements`.

- **Ścieżka pliku:** [`benchmark/scripts/sql-compare.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/sql-compare.sh)
- **Składnia:**
  ```bash
  ./scripts/sql-compare.sh <laravel | nestjs> [liczba_powtórzeń]   # domyślnie: 20
  ```
- **Działanie:**
  - Po wstępnym rozgrzaniu puli połączeń zeruje liczniki `pg_stat_statements_reset()` przed każdym badanym endpointem (`EP1`, `EP2`, `EP2b`, `EP3`, `EP4`, `EP5`, `EP6`, `EP7`, `EP8`, `EP9`) i wykonuje serię 20 powtórzeń bez nagłówka debugującego.
  - Zapisuje dokładną liczbę wywołań (`calls`), średni czas wykonania pojedynczej instrukcji (`mean_ms`), łączny czas SQL przypadający na jedno żądanie HTTP (`ms_per_req`) oraz treść zapytań do pliku `results/smoke/sql-compare-<framework>.txt`.

---

### [`query-count.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/query-count.sh)

Diagnostyka liczby zapytań SQL generowanych przez poszczególne endpointy scenariusza S3 pod kątem wyeliminowania problemu N+1.

- **Ścieżka pliku:** [`benchmark/scripts/query-count.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/query-count.sh)
- **Składnia:**
  ```bash
  ./scripts/query-count.sh <laravel | nestjs>
  ```
- **Działanie:**
  - Wysyła pojedyncze żądania do endpointów `EP1`, `EP2`, `EP2b`, `EP4`, `EP6` oraz `EP8` z nagłówkiem `X-Debug-Queries: 1`.
  - Odczytuje dokładną liczbę zapytań zwróconą w nagłówku odpowiedzi `X-Query-Count` i zapisuje zestawienie do `results/s3/query-count-<framework>.txt`.

---

## 6. Zmienne Środowiskowe i Flagi Wykonawcze

Działanie skryptu [`run-scenario.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh) można konfigurować za pomocą zmiennych środowiskowych:

| Zmienna | Domyślna wartość | Opis |
| :--- | :--- | :--- |
| `ENDPOINTS` | Domyślne dla scenariusza | Lista endpointów objętych badaniem (np. `ENDPOINTS="EP1 EP5"`) |
| `USERS` | Domyślne dla scenariusza | Poziomy współbieżności wirtualnych użytkowników VU (np. `USERS="1 2"`) |
| `REPS` | `10` | Liczba niezależnych powtórzeń pomiarowych |
| `WARMUP` | `60` (S1/S3), `120` (S2) | Czas trwania rozgrzewki w sekundach |
| `DURATION` | `60` (S1/S3), `120` (S2) | Czas trwania właściwego okna pomiarowego w sekundach |
| `RAMPUP` | `10` | Czas rozruchu wątków w JMeterze (odrzucany z analizy) |
| `INTERLEAVE_SEED` | `20261002` | Ziarno generatora pseudolosowego przeplotu kolejności frameworków |
| `DB_POOL_SIZE` | `10` | Rozmiar puli połączeń na proces PM2 w NestJS (`1` dla serii kontrolnej `s2-pool1`) |
| `PM_MAX_CHILDREN` | `4` | Liczba procesów roboczych PHP-FPM w Laravelu (`8` dla `s2-fpm8` lub `{4..40}` w pilotażu) |
| `OUT_NAME` | Wartość `$scenario` | Nazwa katalogu docelowego w `benchmark/results/` |

---

## 7. Struktura Katalogu Wyników (`results/`) i Metadane

Wyniki każdego pojedynczego biegu pomiarowego zapisywane są w ustrukturyzowanej hierarchii katalogów (pełny opis kolumn znajduje się w [`DATA_DICTIONARY.md`](file:///home/wojtek/projekty/badanie/DATA_DICTIONARY.md)):

```
benchmark/results/
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
  "status": "complete",
  "framework": "laravel",
  "scenario": "s1",
  "endpoint": "EP1",
  "mode": "isolated",
  "users": 1,
  "repetition": 1,
  "rampup_s": 10,
  "warmup_s": 60,
  "duration_s": 60,
  "app_cpus": 4.0,
  "postgres_cpus": 4.0,
  "app_memory_mib": 2048.0,
  "db_pool_size": "10",
  "pm_max_children": "4",
  "interleave_seed": 20261002,
  "framework_order": "laravel nestjs",
  "integrity_gate": "pass",
  "row_counts": {
    "orders": 100000,
    "order_items": 299695,
    "reservations": 100000
  }
}
```

Plik ten umożliwia skryptowi [`run-scenario.sh`](file:///home/wojtek/projekty/badanie/benchmark/scripts/run-scenario.sh) bezpieczne wznawianie przerwanych serii oraz natychmiastowe wykrywanie jakichkolwiek modyfikacji kodu źródłowego lub limitów zasobów pomiędzy powtórzeniami.
