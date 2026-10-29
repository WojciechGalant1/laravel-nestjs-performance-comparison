# Benchmark Wydajnościowy: Laravel vs NestJS w Architekturze REST API

Kompleksowe środowisko eksperymentalne do empirycznego porównania wydajności frameworków **Laravel 13 (PHP 8.4)** oraz **NestJS 11 (Node.js 24 LTS)** w architekturze REST API, zrealizowane w kontrolowanym środowisku kontenerowym Docker z wykorzystaniem narzędzia Apache JMeter oraz PostgreSQL 16.

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
8. [Narzędzia Diagnostyczne i Wizualizacja](#8-narz%C4%99dzia-diagnostyczne-i-wizualizacja)
9. [Podsumowanie Wyników Empirycznych i Werdyktów Hipotez ($n = 10$)](#9-podsumowanie-wynik%C3%B3w-empirycznych-i-werdykt%C3%B3w-hipotez-n--10)

---

## Dokumentacja Projektu (Indeks Dokumentów)

Kompletna dokumentacja badania oraz manuskryptu została podzielona na dedykowane moduły techniczne i naukowe:

| Dokument | Ścieżka pliku | Zakres i zawartość |
| :--- | :--- | :--- |
| **Słownik Danych i Wyniki** | [`DATA_DICTIONARY.md`](file:///home/wojtek/projekty/badanie/DATA_DICTIONARY.md) | Struktura katalogu `results/`, legenda nazewnictwa oraz pełna specyfikacja kolumn plików CSV i JSON (`results.jtl`, `stats.csv`, `meta.json`, `runs.csv`, `summary.csv`). |
| **Baza Danych** | [`DATABASE.md`](file:///home/wojtek/projekty/badanie/DATABASE.md) | Schemat relacyjny PostgreSQL 16 (diagram ERD Mermaid), słowniki i tabele transakcyjne, deterministyczny seeder (`mt_srand(20260101)`) oraz mechanizmy migawek `*_template`. |
| **Skrypty i Pipeline** | [`SCRIPTS.md`](file:///home/wojtek/projekty/badanie/SCRIPTS.md) | Dokumentacja orkiestracji eksperymentów (`run-main.sh`, `run-scenario.sh`, `run-s2-sensitivity.sh`, `run-fpm-pilot.py`), analizy statystycznej Bootstrap 10k (`summarize.py`) oraz wykresów (`plot_s*.py`). |
| **Aplikacja Laravel** | [`benchmark/apps/laravel-app/README.md`](file:///home/wojtek/projekty/badanie/benchmark/apps/laravel-app/README.md) | Architektura stosu PHP 8.4 + OPcache/JIT, procesy PHP-FPM (`PM_MAX_CHILDREN`), uwierzytelnianie `ClaimJwtGuard`, specyfikacja endpointów `EP0`–`EP9` (wraz z `EP2b`) oraz [OpenAPI 3.0](file:///home/wojtek/projekty/badanie/benchmark/apps/laravel-app/openapi.yaml). |
| **Aplikacja NestJS** | [`benchmark/apps/nestjs-app/README.md`](file:///home/wojtek/projekty/badanie/benchmark/apps/nestjs-app/README.md) | Architektura stosu Node.js 24 + PM2 Cluster Mode, konfiguracja TypeORM (`relationLoadStrategy: 'query'`), specyfikacja endpointów `EP0`–`EP9` (wraz z `EP2b`) oraz [OpenAPI 3.0](file:///home/wojtek/projekty/badanie/benchmark/apps/nestjs-app/openapi.yaml). |
| **Artykuł Naukowy (8 stron)** | [`dokumenty/przegladEng.md`](file:///home/wojtek/projekty/badanie/dokumenty/przegladEng.md)<br>[`dokumenty/metodyka_short.md`](file:///home/wojtek/projekty/badanie/dokumenty/metodyka_short.md)<br>[`dokumenty/results.md`](file:///home/wojtek/projekty/badanie/dokumenty/results.md)<br>[`dokumenty/discussion.md`](file:///home/wojtek/projekty/badanie/dokumenty/discussion.md) | Manuskrypt publikacji naukowej w języku angielskim (Sekcje 1–2: Wstęp i przegląd literatury; Sekcja 3: Metodyka; Sekcja 4: Wyniki; Sekcje 5–6: Dyskusja oraz Wnioski i prace przyszłe). |
| **Wyniki Rozszerzone i Pilotaże (Praca Magisterska)** | [`results.md`](file:///home/wojtek/projekty/badanie/results.md) | Kompletne zestawienie wyników spoza artykułu (poziomy nasycenia 4 i 10 VU, pełna siatka `pm.max_children` $\in \{4..40\}$, `DB_POOL_SIZE=1` na EP7, profilowanie `pg_stat_statements` oraz wszystkie kampanie pilotażowe). |

---

## 1. Wymagania sprzętowe i Szybki Start (Quick Start)

### Wymagania sprzętowe i systemowe
- **Procesor:** Min. 12 vCPU (stanowisko badawcze: AMD Ryzen 7 5800H – 8 rdzeni / 16 wątków logicznych).
- **Pamięć RAM:** Min. 16 GB RAM ($\ge 15.6$ GB przydzielone dla WSL2 / Linuksa).
- **System operacyjny:** Linux (Ubuntu 22.04 LTS) lub Windows 11 z WSL2 (jądro $\ge 6.6$).
- **Oprogramowanie:** Docker Engine $\ge 24.0$ z Docker Compose v2, Python 3.10+, Bash, `curl`, `jq`.

> **Zasada izolacji:** Podczas testów uruchomiony jest w danym momencie tylko **jeden stos aplikacyjny** (Laravel lub NestJS), dzięki czemu procesy nie konkurują o te same rdzenie procesora i pamięć RAM. Generator JMeter działa w dedykowanym kontenerze w sieci mostkowej Docker (`bridge`), nie obciążając budżetu CPU aplikacji.

### Szybki Start (Krok po kroku)

```bash
cd benchmark

# 1. Konfiguracja zmiennych środowiskowych
cp .env.example .env

# 2. Inicjalizacja i zasilenie bazy danych (migracje + deterministyczny seeder + szablony *_template)
./scripts/db-setup.sh

# 3. Wygenerowanie danych pomocniczych dla planów JMeter (zakresy ID, stronicowanie)
./scripts/jmeter-data.sh

# 4. Uruchomienie pełnej serii pomiarowej (n=10 powtórzeń dla S1, S2, S2-pool1, S3)
./scripts/run-main.sh all

# 5. (Opcjonalnie) Uruchomienie symetrycznej serii wrażliwości S2 (DB_POOL_SIZE=1 oraz PM_MAX_CHILDREN=8)
./scripts/run-s2-sensitivity.sh
```

Skrypt `scripts/run-main.sh` jest w pełni wznawialny (**resumable**): po przerwaniu pomija już ukończone powtórzenia (zweryfikowane sumą kontrolną w `meta.json`).

---

## 2. Architektura i Symetria Środowiska

Aby wyizolować narzut samych frameworków i ich modeli wykonawczych (synchroniczny proces roboczy PHP-FPM vs asynchroniczna pętla zdarzeń Node.js w klastrze PM2), wdrożono ścisłą symetrię architektoniczną:

| Warstwa / Komponent | Stos Laravel | Stos NestJS |
| :--- | :--- | :--- |
| **System bazowy obrazu** | Debian 12 Bookworm (`php:8.4-fpm-bookworm`) | Debian 12 Bookworm (`node:24-bookworm-slim`) |
| **Wersja platformy** | PHP 8.4 (OPcache 256 MB + JIT `tracing` 128 MB) | Node.js 24.21.0 LTS (V8 engine) |
| **Zarządca procesów** | PHP-FPM (`pm = static`, domyślnie 4 procesy potomne; kontrola S2: 8–40) | PM2 Cluster Mode (4 instancje robocze – 1 Event Loop / vCPU) |
| **Przydział zasobów (cgroups)** | 4 vCPU, 2 GiB RAM | 4 vCPU, 2 GiB RAM |
| **Reverse Proxy** | Nginx 1.25 (FastCGI, `access_log off`, limit 1 vCPU, 256 MiB RAM) | Nginx 1.25 (HTTP keepalive 64, `access_log off`, limit 1 vCPU, 256 MiB RAM) |
| **Połączenia z bazą** | 1 stałe / worker (`PDO::ATTR_PERSISTENT`, domyślnie 4 łącznie) | Pula 10 / worker (domyślnie max 40); kontrola S2 (`s2-pool1`): 1 / worker (4 łącznie) |
| **Strategia ORM** | Eloquent (Active Record, eager loading w osobnych zapytaniach `WHERE IN`) | TypeORM (`relationLoadStrategy: 'query'`, koperta stronicowania Laravel, `snake_case`) |
| **Baza danych** | PostgreSQL 16 (4 vCPU, 2 GiB RAM, `max_connections = 100`, dane w RAM) | Identyczna baza sklonowana z szablonu `*_template` |

---

## 3. Struktura Repozytorium

```
badanie/
├── README.md                    # Główna dokumentacja projektu i podsumowanie wyników
├── DATABASE.md                  # Specyfikacja schematu PostgreSQL 16, ERD i determinizmu seedera
├── DATA_DICTIONARY.md           # Słownik danych i specyfikacja kolumn plików wynikowych
├── SCRIPTS.md                   # Dokumentacja skryptów wykonawczych, analitycznych i wykresów
├── results.md                   # Zbiorcze opracowanie wyników spoza artykułu i badań pilotażowych (pod pracę mgr)
│
├── dokumenty/                   # Manuskrypt artykułu naukowego, wykresy i uporządkowane notatki badawcze
│   ├── przegladEng.md           # Sekcje 1–2 artykułu: Introduction & Related Work
│   ├── metodyka_short.md        # Sekcja 3 artykułu: Methodology (Research Plan, Tools, Object, Stand, Method)
│   ├── results.md               # Sekcja 4 artykułu: Empirical Results (H1, H2, H3)
│   ├── discussion.md            # Sekcje 5–6 artykułu: Discussion & Conclusions and future works
│   ├── figures/                 # Wykresy publikacyjne (fig1_s1_baseline.png, fig2_s2_..., fig3_s3_...)
│   └── notatki/                 # Uporządkowana baza wiedzy teoretycznej i architektonicznej (01..05)
│
└── benchmark/                   # Środowisko wykonawcze benchmarku
    ├── .env.example             # Szablon zmiennych środowiskowych
    ├── docker-compose.yml       # Definicja usług Docker z profilami (laravel, nestjs, setup, loadtest)
    ├── apps/
    │   ├── laravel-app/         # Aplikacja backendowa Laravel 13 (PHP 8.4)
    │   ├── nestjs-app/          # Aplikacja backendowa NestJS 11 (Node.js 24 LTS)
    │   └── nginx/               # Konfiguracje reverse proxy (laravel.conf, nestjs.conf)
    ├── jmeter/
    │   ├── s1.jmx, s2.jmx, s3.jmx # Plany testowe dla scenariuszy S1, S2 i S3
    │   └── data/                # Wygenerowane zakresy ID (ranges.properties, available_menu_items.csv)
    ├── scripts/                 # Skrypty orkiestracji, analizy Bootstrap 10k, profilowania i wykresów
    └── results/                 # Surowe i zagregowane wyniki pomiarów (s1, s2, s2-pool1, s3, smoke)
```

---

## 4. Konfiguracja Środowiska i Runtimów

### Plik `.env` i zmienne sterujące
- `BENCH_NOW="2026-09-01 00:00:00"`: Zamrożony znacznik czasu odniesienia, gwarantujący identyczność generowanych danych i agregacji `EP6` (dokładnie 33 469 zamówień w oknie 30 dni).
- `JWT_SECRET`, `JWT_TTL=3600`: Współdzielony klucz HS256 i czas życia tokenu.
- `APP_CPUS=4`, `APP_MEMORY=2g` oraz `DB_CPUS=4`, `DB_MEMORY=2g`: Limity zasobów cgroups dla kontenerów aplikacji i bazy danych.
- `DB_POOL_SIZE=10`: Rozmiar puli połączeń na proces roboczy w NestJS (w serii kontrolnej `s2-pool1` nadpisywany dynamicznie na `1`).
- `PM_MAX_CHILDREN=4`: Liczba procesów roboczych PHP-FPM w Laravelu (w serii kontrolnej `s2-fpm8` nadpisywana na `8`, a w pilotażu `run-fpm-pilot.py` badana dla `{4, 8, 16, 24, 32, 40}`).

---

## 5. Determinizm Danych i Zarządzanie Bazą

> Szczegółowy opis schematu relacyjnego, relacji 1:N / N:M, diagramu ERD oraz procedur seedera znajduje się w dokumencie [`DATABASE.md`](file:///home/wojtek/projekty/badanie/DATABASE.md).

- **Ziarno generatora liczb pseudolosowych:** Ustalony seed `mt_srand(20260101)` i `fake()->seed(20260101)`.
- **Rozmiary tabel:**
  - Tabele słownikowe: `users` (200), `tables` (200), `ingredients` (200), `dishes` (500), `menu_items` (500, z czego 445 dostępnych).
  - Tabela asocjacyjna: `dish_ingredients` (2 000 wierszy, relacja N:M).
  - Tabele transakcyjne: `orders` (100 000 wierszy), `order_items` (**299 695** wierszy) — łącznie **401 895 wierszy** w 8 tabelach wykorzystywanych w artykule naukowym (oraz dodatkowo 100 000 wierszy w tabeli `reservations` z indeksem GiST dla pracy magisterskiej, co daje łącznie **501 895 wierszy** w 9 tabelach).
- **Szybki reset bazy (`scripts/db-reset.sh`):** Przed każdym pojedynczym przebiegiem baza danych jest odtwarzana z migawki wzorcowej (`CREATE DATABASE ... TEMPLATE ..._template`), a kontenery aplikacji i proxy są restartowane.

---

## 6. Pipeline Wykonawczy i Orkiestracja Testów

> Szczegółowy opis działania skryptów orkiestracyjnych znajduje się w [`SCRIPTS.md`](file:///home/wojtek/projekty/badanie/SCRIPTS.md).

Dla każdego endpointu, poziomu współbieżności i powtórzenia ($n = 1..10$):
1. **Przeplot (Interleaving):** Kolejność uruchamiania frameworków w każdym powtórzeniu jest pseudolosowo tasowana (`INTERLEAVE_SEED=20261002`), eliminując wpływ dryftu termicznego.
2. **Faza rozgrzewki (Warm-Up):** 60 s dla S1 i S3; 120 s dla S2 (próbki odrzucane).
3. **Faza pomiarowa (Measurement):** 60 s dla S1 i S3; 120 s dla S2 (pierwsze 10 s ramp-upu jest obcinane, pozostawiając czyste okno *steady-state*).
4. **Bramki integralności (Integrity Gates):** Automatyczna weryfikacja niezmienniczości wierszy dla odczytów/aktualizacji oraz zgodności 1:1 liczby nowych rekordów w `orders` i `order_items` z liczbą kodów HTTP 201 na `EP7`.

---

## 7. Przetwarzanie Wyników i Analiza Statystyczna

Analiza danych pomiarowych jest wykonywana przez pakiet [`benchmark/scripts/summarize.py`](file:///home/wojtek/projekty/badanie/benchmark/scripts/summarize.py):

```bash
python3 scripts/summarize.py s1
python3 scripts/summarize.py s2
python3 scripts/summarize.py s2-pool1
python3 scripts/summarize.py s3
```

### Reguły weryfikacji hipotez badawczych (Bootstrap 10 000 prób, `BOOTSTRAP_SEED = 20261002`)

1. **Reguła poprawności niskiego obciążenia (*Low-Load Validity Rule*):**
   Poziom współbieżności $N$ należy do zbioru niskiego obciążenia (dla S1 i S3: 1 oraz 2 VU), jeśli dla obu frameworków: (a) skalowanie przepustowości $X(N)/(N \cdot X(1)) \ge 0.80$, (b) średnie CPU aplikacji $< 80\%$ limitu kontenera oraz (c) średnie CPU PostgreSQL $< 80\%$ limitu kontenera.
2. **Hipoteza H1 (Równoważność bazowa w S1 na `EP1` i `EP5`):**
   $$\Delta p_{95} = \frac{|p_{95,L} - p_{95,N}|}{(p_{95,L} + p_{95,N}) / 2} \times 100\%$$
   Hipoteza **potwierdzona**, gdy górna granica 95% CI $\Delta p_{95} \le 15\%$ przy wskaźniku błędów $< 1\%$.
3. **Hipoteza H2 (Degradacja skalowalności w S2 pod stresem na `EP3` oraz uzupełniająco `EP7`):**
   $$r = \frac{s_L}{s_N}$$
   gdzie $s_L, s_N$ to nachylenia regresji liniowej (OLS) mediany opóźnienia $p_{95}$ względem współbieżności $N \in \{200, 500, 1000\}$ VU. Hipoteza **potwierdzona**, gdy dolna granica 95% CI $r > 1.0$.
4. **Hipoteza H3 (Narzut złożoności relacyjnej w S3 na `EP2` względem kontroli na tej samej tabeli `EP2b`):**
   Estymator Difference-in-Differences względem pozbawionego relacji punktu odniesienia na tej samej tabeli (`EP2b: GET /api/menu-items/plain`):
   $$D_k = (p_{95,L}(k) - p_{95,N}(k)) - (p_{95,L}(\text{EP2b}) - p_{95,N}(\text{EP2b}))$$
   Zgodnie z trójwartościową regułą decyzyjną przy 2 VU: hipoteza jest **potwierdzona (*supported*)**, jeśli dolna granica 95% CI $D_{\text{EP2}} > 2.0\text{ ms}$ (oraz $D_{\text{EP2}} > 0$ przy 1 VU); **odrzucona (*rejected*)**, jeśli górna granica 95% CI $\le 0.0\text{ ms}$; **nierozstrzygnięta (*inconclusive*)**, jeśli przedział ufności obejmuje próg $2.0\text{ ms}$ przy dodatniej górnej granicy.

---

## 8. Narzędzia Diagnostyczne i Wizualizacja

W katalogu [`benchmark/scripts/`](file:///home/wojtek/projekty/badanie/benchmark/scripts/) znajdują się narzędzia diagnostyczne i wizualizacyjne:
- **`scripts/sql-compare.sh <laravel|nestjs>`:** Profiluje rzeczywisty czas wykonania poszczególnych zapytań SQL w silniku PostgreSQL (`pg_stat_statements`) dla wszystkich endpointów `EP1`–`EP9` (wraz z `EP2b`).
- **`scripts/query-count.sh <laravel|nestjs>`:** Weryfikuje symetrię liczby zapytań SQL w scenariuszu S3 za pomocą nagłówka `X-Debug-Queries: 1` (`X-Query-Count`).
- **`scripts/golden-write-check.sh <laravel|nestjs>`:** Sprawdza bajtową identyczność rekordów zapisywanych przez `EP5`, `EP7` i `EP9`.
- **`scripts/plot_s1.py`, `plot_s2.py`, `plot_s3.py`:** Generują wykresy publikacyjne do katalogu `dokumenty/figures/`.

---

## 9. Podsumowanie Wyników Empirycznych i Werdyktów Hipotez ($n = 10$)

Pełna analiza znajduje się w rozdziale wynikowym artykułu ([`dokumenty/results.md`](file:///home/wojtek/projekty/badanie/dokumenty/results.md)) oraz w opracowaniu rozszerzonym pod pracę magisterską ([`results.md`](file:///home/wojtek/projekty/badanie/results.md)). Wskaźnik błędów HTTP/timeout wyniósł **0.00%** we wszystkich przebiegach serii głównej.

| Hipoteza i Scenariusz | Główny Endpoint i Poziomy VU | Kluczowe Wyniki Empiryczne ($n = 10$) | Przedział Ufności (95% Bootstrap CI) | Werdykt Formalny |
| :--- | :--- | :--- | :--- | :---: |
| **H1: Równoważność bazowa**<br>*(Scenariusz S1)* | `EP1` *(odczyt)* i `EP5` *(zapis)*<br>@ 1 VU, 2 VU | • `EP1` (2 VU): $p_{95} = 8.0\text{ ms}$ (Lar) vs $2.0\text{ ms}$ (Nest); $290.8$ vs $1519.8\text{ RPS}$ ($5.23\times$)<br>• `EP5` (2 VU): $p_{95} = 8.0\text{ ms}$ (Lar) vs $4.0\text{ ms}$ (Nest); $328.7$ vs $726.8\text{ RPS}$ ($2.21\times$)<br>• Koszt CPU/req: $4.72–6.20\text{ ms}$ (Lar) vs $0.93–1.33\text{ ms}$ (Nest)<br>• Pamięć RAM (peak): $\sim 51\text{ MiB}$ (Lar) vs $\sim 701–728\text{ MiB}$ (Nest) | • `EP1`: $\Delta p_{95} = 120.0\%$<br>$[111.1\%, 120.0\%] > 15\%$<br>• `EP5`: $\Delta p_{95} = 66.7\%$<br>$[60.9\%, 66.7\%] > 15\%$ | **ODRZUCONA**<br>*(Rejected)* |
| **H2: Degradacja pod wysokim obciążeniem**<br>*(Scenariusz S2)* | **Główny (odczyt):** `EP3`<br>**Uzupełniający (zapis):** `EP7`<br>@ 200, 500, 1000 VU | • **EP3 (plateau bazy ~145 RPS):** nachylenie $s_L = 6.80\text{ ms/VU}$ vs $s_N = 7.65\text{ ms/VU}$ (40 połączeń NestJS dławi PG przy $99.5\%$ CPU)<br>• **Kontrola wrażliwości EP3 (`DB_POOL_SIZE=1`, 4 conn):** przepustowość NestJS rośnie o **$+25.8\%–39.3\%$** ($201.4\text{ RPS}$ @ 200 VU), a $p_{95}$ @ 1000 VU spada do $6253.5\text{ ms}$<br>• **Kontrola PHP-FPM (`pm.max_children`):** optimum przy **8 workerach** ($161.4\text{ RPS}$ na EP3, $507.6\text{ RPS}$ na EP7 przy $99.9\%$ CPU); przy **40 workerach** dławienie bazy na EP3 ($117.2\text{ RPS}$, $p_{95} > 10\text{ s}$)<br>• **EP7 (zapis transakcyjny):** NestJS osiąga $4.7\times–6.9\times$ wyższą przepustowość ($1974–2194\text{ RPS}$ vs $286–453\text{ RPS}$); nachylenie $s_L = 4.02$ vs $s_N = 0.56\text{ ms/VU}$ | • **EP3 (główny):**<br>$r = 0.889$<br>$[0.807, 0.909] < 1.0$<br>• **EP7 (zapis):**<br>$r = 7.19$<br>$[6.672, 7.441] > 1.0$ | **ODRZUCONA**<br>na głównym celu odczytowym `EP3`<br>*(potwierdzona 7.19× szybsza degradacja Laravela na zapisie `EP7`)* |
| **H3: Narzut złożoności relacyjnej**<br>*(Scenariusz S3)* | **Główny:** `EP2` vs `EP2b`<br>**Obserwacje:** `EP4`, `EP6`<br>@ 1 VU, 2 VU | • `EP2b` *(0 rel, 2 VU)*: $p_{95} = 7.5\text{ ms}$ vs $2.0\text{ ms}$ ($S_{\text{EP2b}} = 5.5\text{ ms}$)<br>• `EP2` *(1 rel, 2 VU)*: $p_{95} = 10.0\text{ ms}$ vs $3.0\text{ ms}$ ($S_{\text{EP2}} = 7.0\text{ ms}$); kontrast ciągły Mean $D = +1.81\text{ ms}$, CPU/req $D = +1.72\text{ ms}$<br>• `EP4` *(3-lvl nested, 2 VU)*: $D_{\text{EP4}} = +1.00\text{ ms}$ ($[0.00, 2.50]\text{ ms}$)<br>• `EP6` *(agregacja SQL, 2 VU)*: konwergencja czasów ($161.0\text{ ms}$ vs $149.5\text{ ms}$, CI obejmuje zero) | • `EP2` (2 VU):<br>$D_{\text{EP2}} = +1.50\text{ ms}$<br>$[1.00, 3.00]\text{ ms}$<br>*(dolna granica $1.00 \le 2.0\text{ ms}$, górna $3.00 > 0\text{ ms}$)* | **NIEROZSTRZYGNIĘTA**<br>*(Inconclusive – efekt dodatni $\sim 1.5–1.8\text{ ms}$, tuż poniżej progu $2.0\text{ ms}$)* |
