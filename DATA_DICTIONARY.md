# Słownik Danych i Struktura Wyników Benchmarku (Data Dictionary)

Kompleksowa dokumentacja schematów danych, formatów telemetrycznych, logów pomiarowych oraz przetworzonych tabel analitycznych w projekcie porównania wydajności frameworków **Laravel** i **NestJS**.

Dokument definiuje architekturę katalogu wyników `results/`, zasady nazewnictwa oraz pełną specyfikację semantyczną każdej kolumny i właściwości w plikach CSV oraz JSON generowanych przez narzędzia Apache JMeter, Docker Engine oraz skrypty analityczne Python.

---

## Spis Treści

1. [Hierarchia i Struktura Katalogu Wyników (`results/`)](#1-hierarchia-i-struktura-katalogu-wyników-results)
2. [Legenda Schematu Nazewnictwa Plików i Katalogów](#2-legenda-schematu-nazewnictwa-plików-i-katalogów)
3. [Formaty Danych Surowych i Telemetrycznych](#3-formaty-danych-surowych-i-telemetrycznych)
   - [Surowy ślad próbkowania JMeter: `results.jtl`](#surowy-ślad-próbkowania-jmeter-resultsjtl)
   - [Telemetria zasobów Docker: `stats.csv`](#telemetria-zasobów-docker-statscsv)
   - [Metadane przebiegu i sumy kontrolne: `meta.json`](#metadane-przebiegu-i-sumy-kontrolne-metajson)
4. [Formaty Danych Przetworzonych (Pipeline Analityczny)](#4-formaty-danych-przetworzonych-pipeline-analityczny)
   - [Tabela pojedynczych powtórzeń: `runs.csv`](#tabela-pojedynczych-powtórzeń-runscsv)
   - [Tabela zbiorcza i agregacje statystyczne: `summary.csv`](#tabela-zbiorcza-i-agregacje-statystyczne-summarycsv)
5. [Pliki Pomocnicze i Diagnostyczne](#5-pliki-pomocnicze-i-diagnostyczne)
   - [Parametry wejściowe JMeter: `ranges.properties` i `available_menu_items.csv`](#parametry-wejściowe-jmeter)
   - [Raporty inspekcji ORM: `sql-compare` i `query-count`](#raporty-inspekcji-orm)

---

## 1. Hierarchia i Struktura Katalogu Wyników (`results/`)

Wszystkie artefakty generowane w trakcie wykonywania eksperymentu zapisywane są w ścisłym drzewie katalogów, gwarantującym pełną separację scenariuszy, frameworków, punktów końcowych, poziomów obciążenia oraz niezależnych powtórzeń ($n = 10$).

```
results/
├── s1/                                 # Katalog scenariusza (s1, s2, s2-pool1, s3)
│   ├── runs.csv                        # Przetworzone dane ze wszystkich n=10 powtórzeń (summarize.py)
│   ├── summary.csv                     # Zagregowane mediany i odchylenia standardowe (summarize.py)
│   │
│   ├── laravel/                        # Podkatalog frameworka (laravel / nestjs)
│   │   └── EP1/                        # Podkatalog badanego endpointu (EP1 .. EP10)
│   │       ├── vu1/                    # Poziom współbieżności wirtualnych użytkowników (vu1, vu2, ...)
│   │       │   ├── rep01/              # Pojedyncze powtórzenie pomiarowe (rep01 .. rep10)
│   │       │   │   ├── results.jtl     # Surowy ślad zapytań HTTP zarejestrowany przez JMeter (CSV)
│   │       │   │   ├── stats.csv       # Ślad telemetryczny zużycia CPU i RAM z docker stats (CSV)
│   │       │   │   ├── meta.json       # Środowiskowe metadane, parametry wykonawcze i bramki integralności
│   │       │   │   ├── warmup.log      # Log konsolowy fazy rozgrzewki (warm-up)
│   │       │   │   └── jmeter.log      # Dziennik zdarzeń silnika Apache JMeter
│   │       │   ├── ...
│   │       │   └── rep10/
│   │       └── vu2/
│   │           └── ...
│   └── nestjs/
│       └── ...
├── s2/
├── s2-pool1/
├── s3/
└── smoke/                              # Wyniki testów dymnych i weryfikacji integralności
    ├── sql-compare-laravel.txt
    ├── sql-compare-nestjs.txt
    └── golden-write-*.json
```

---

## 2. Legenda Schematu Nazewnictwa Plików i Katalogów

Poniższa tabela objaśnia skróty, tokeny i reguły nazewnicze stosowane w strukturze katalogów i plikach wyjściowych:

| Segment / Wzorzec | Przykłady | Znaczenie semantyczne |
| :--- | :--- | :--- |
| `<scenario>` | `s1`, `s2`, `s2-pool1`, `s3` | **Identyfikator scenariusza badawczego:**<br>• `s1`: Baseline CRUD (niskie obciążenie, 1 i 2 VU)<br>• `s2`: Stres i skalowalność współbieżna (200, 500, 1000 VU)<br>• `s2-pool1`: Wariant kontrolny NestJS z rozmiarem puli połączeń równym 1<br>• `s3`: Złożoność relacyjna i podatność ORM (1 i 2 VU) |
| `<framework>` | `laravel`, `nestjs` | **Badany stos technologiczny:**<br>• `laravel`: PHP 8.4 + OPcache/JIT + PHP-FPM + Eloquent<br>• `nestjs`: Node.js 24 + PM2 Cluster + TypeORM |
| `<endpoint>` | `EP1` .. `EP10` | **Identyfikator badanego punktu końcowego API:**<br>• `EP1`: Prosty odczyt jednostkowy (`GET /dishes/{id}`)<br>• `EP2`: Odczyt relacyjny szeroki (`GET /orders/{id}` z 4 relacjami)<br>• `EP3`: Wyszukiwanie z filtrowaniem i stronicowaniem (`GET /menu-items`)<br>• `EP4`: Wyszukiwanie relacyjne wielotabelowe (`GET /orders?status=...`)<br>• `EP5`: Operacja przeliczeniowa CPU (`POST /promotions/calculate`)<br>• `EP6`: Agregacja analityczna SQL (`GET /reports/daily-sales`)<br>• `EP7`: Złożony zapis transakcyjny (`POST /orders`)<br>• `EP8`: Prosta modyfikacja rekordu (`PUT /tables/{id}/status`)<br>• `EP9`: Usunięcie rekordu (`DELETE /reservations/{id}`)<br>• `EP10`: Autoryzacja i weryfikacja JWT (`GET /auth/me`) |
| `vu<N>` | `vu1`, `vu2`, `vu4`, `vu10`, `vu200`, `vu500`, `vu1000` | **Współbieżność (Virtual Users):** Liczba równoległych wątków roboczych symulowanych przez generator JMeter. |
| `rep<NN>` | `rep01` .. `rep10` | **Numer powtórzenia:** Dwucyfrowy identyfikator niezależnego biegu pomiarowego w serii ($n=10$). |
| `results.jtl` | `results.jtl` | Surowy log próbek HTTP wygenerowany przez Apache JMeter w formacie CSV. |
| `stats.csv` | `stats.csv` | Log telemetrii zasobów systemowych rejestrowany przez `docker stats` co $\sim 0.5$ s. |
| `meta.json` | `meta.json` | Środowiskowy rekord JSON z parametrami biegu, commitami Git i weryfikacją bazy. |
| `runs.csv` | `runs.csv` | Spłaszczona tabela wszystkich pojedynczych biegów pomiarowych po odrzuceniu ramp-upu. |
| `summary.csv` | `summary.csv` | Tabela zagregowanych median i odchyleń standardowych ($n=10$) dla scenariusza. |

---

## 3. Formaty Danych Surowych i Telemetrycznych

### Surowy ślad próbkowania JMeter: `results.jtl`

Plik generowany w trybie bezgłowym (CLI) przez Apache JMeter. Zapisywany jako plik CSV z nagłówkiem (zgodnie z konfiguracją w [`benchmark/jmeter/run.properties`](file:///home/user/projekty/badanie/benchmark/jmeter/run.properties)).

| Kolumna | Typ danych | Jednostka | Opis |
| :--- | :--- | :--- | :--- |
| `timeStamp` | Liczba całkowita | ms (epoch) | Znacznik czasu uniksowego (w milisekundach) rozpoczęcia żądania HTTP. |
| `elapsed` | Liczba całkowita | ms | Całkowity czas obsługi żądania (czas od wysłania pierwszego bajtu do odebrania ostatniego bajtu odpowiedzi). |
| `label` | Ciąg znaków | - | Identyfikator samplera JMeter (np. `EP1`, `EP2`, lub techniczny `SETUP_login`). |
| `responseCode` | Ciąg znaków | - | Kod statusu odpowiedzi HTTP (np. `200`, `201`, `400`, `401`, `404`, `500`). |
| `responseMessage` | Ciąg znaków | - | Komunikat tekstowy powiązany ze statusem HTTP (np. `OK`, `Created`, `Unauthorized`). |
| `success` | Wartość logiczna | - | Flaga powodzenia asercji i kodu odpowiedzi (`true` dla poprawnych kodów HTTP, `false` w przypadku błędu). |
| `failureMessage` | Ciąg znaków | - | Treść komunikatu błędu w przypadku niepowodzenia asercji odpowiedzi JMeter. |
| `bytes` | Liczba całkowita | bajty | Całkowity rozmiar odebranej treści odpowiedzi HTTP (nagłówki + ciało odpowiedzi). |
| `Latency` | Liczba całkowita | ms | Czas do pierwszego bajtu (TTFB – *Time to First Byte*), czyli czas oczekiwania na rozpoczęcie transmisji zwrotnej. |
| `Connect` | Liczba całkowita | ms | Czas nawiązania połączenia sieciowego TCP (w tym ewentualny handshake). |
| `allThreads` | Liczba całkowita | - | Łączna liczba aktywnych wątków (wirtualnych użytkowników) we wszystkich grupach testowych. |
| `grpThreads` | Liczba całkowita | - | Liczba aktywnych wątków w bieżącej grupie testowej JMeter. |

---

### Telemetria zasobów Docker: `stats.csv`

Plik tworzony w tle przez pętlę strumieniującą polecenia `docker stats --format '{{json .}}'` w skrypcie [`run-scenario.sh`](file:///home/user/projekty/badanie/benchmark/scripts/run-scenario.sh). Monitoruje kontenery aplikacji (`laravel`/`nestjs`), serwer proxy (`nginx`), bazę (`postgres`) oraz generator (`jmeter`).

| Kolumna | Typ danych | Jednostka | Opis |
| :--- | :--- | :--- | :--- |
| `epoch` | Liczba zmiennoprzecinkowa | sekundy | Znacznik czasu uniksowego WSL (`$EPOCHREALTIME`) z dokładnością do mikrosekund w momencie odczytu próbki. |
| `name` | Ciąg znaków | - | Nazwa monitorowanego kontenera Docker (np. `benchmark-laravel-1`, `benchmark-postgres-1`). |
| `cpu_perc` | Liczba zmiennoprzecinkowa | % | Chwilowe zużycie procesora przez kontener (100% oznacza pełne wykorzystanie 1 logicznego rdzenia vCPU). |
| `mem_usage` | Ciąg znaków | format sufiksowy | Bieżące zużycie pamięci operacyjnej z jednostką (np. `85.4MiB`, `1.2GiB`). Przeliczane automatycznie na MiB. |
| `mem_limit` | Ciąg znaków | format sufiksowy | Przydzielony kontenerowi limit pamięci cgroups (np. `2GiB`). |
| `mem_perc` | Liczba zmiennoprzecinkowa | % | Procentowe wykorzystanie przydzielonego limitu pamięci RAM kontenera. |

---

### Metadane przebiegu i sumy kontrolne: `meta.json`

Kluczowy dokument JSON generowany na zakończenie każdego powtórzenia pomiarowego. Gwarantuje powtarzalność, integralność środowiskową oraz umożliwia bezpieczne wznawianie przerwanych testów.

| Klucz JSON | Typ danych | Przykładowa wartość | Opis semantyczny |
| :--- | :--- | :--- | :--- |
| `status` | string | `"complete"` | Status wykonania przebiegu (`"complete"` oznacza bieg prawidłowy i uwzględniany w analizie). |
| `framework` | string | `"laravel"` | Nazwa badanego frameworka (`"laravel"` lub `"nestjs"`). |
| `scenario` | string | `"s1"` | Identyfikator scenariusza testowego (`"s1"`, `"s2"`, `"s2-pool1"`, `"s3"`). |
| `endpoint` | string | `"EP1"` | Badany punkt końcowy (lub `"all"` w planach zbiorczych). |
| `mode` | string | `"single"` | Tryb wykonania planu testowego (`"single"` lub `"mixed"`). |
| `users` | int | `1` | Liczba wirtualnych użytkowników (VU) w badanym biegu. |
| `repetition` | int | `1` | Numer powtórzenia pomiarowego ($1..10$). |
| `rampup_s` | int | `10` | Czas rozruchu wątków JMeter w sekundach (okres odrzucany podczas analizy). |
| `warmup_s` | int | `60` | Czas trwania rozgrzewki kontenera w sekundach (próbki nie trafiają do `results.jtl`). |
| `duration_s` | int | `60` | Całkowity zaplanowany czas trwania pomiaru właściwego w sekundach. |
| `measurement_started` | float | `1776000000.123` | Znacznik czasu uniksowego (sekundy) rozpoczęcia właściwego okna pomiarowego. |
| `measurement_finished`| float | `1776000060.456` | Znacznik czasu uniksowego (sekundy) zakończenia okna pomiarowego. |
| `clock_offset_s` | float | `0.002` | Zmierzona różnica zegara systemowego pomiędzy środowiskiem hosta a kontenerami Docker. |
| `app_cpus` | float | `4.0` | Efektywny przydział rdzeni vCPU dla kontenera aplikacji odczytany z cgroups. |
| `postgres_cpus` | float | `4.0` | Efektywny przydział rdzeni vCPU dla kontenera PostgreSQL odczytany z cgroups. |
| `app_memory_mib` | float | `2048.0` | Limit pamięci RAM kontenera aplikacji w MiB odczytany przez `docker inspect`. |
| `db_pool_size` | string | `"10"` | Rozmiar puli połączeń do bazy danych skonfigurowany w środowisku aplikacji. |
| `app_image` | string | `"sha256:abc..."` | Pełny identyfikator SHA256 skompilowanego obrazu kontenera aplikacji. |
| `interleave_seed` | int | `20261002` | Bazowe ziarno generatora pseudolosowego przeplotu frameworków. |
| `framework_order` | string | `"laravel nestjs"` | Rzeczywista kolejność uruchomienia frameworków w danym powtórzeniu. |
| `git_commit` | string | `"f3a8b2..."` | Hash commita Git repozytorium w momencie wykonania biegu. |
| `laravel_app_tree` | string | `"d41d8c..."` | Suma kontrolna drzewa katalogu `apps/laravel-app` (wykrywa jakiekolwiek modyfikacje kodu). |
| `nestjs_app_tree` | string | `"e2fc71..."` | Suma kontrolna drzewa katalogu `apps/nestjs-app`. |
| `integrity_gate` | string | `"pass"` | Wynik weryfikacji bramki integralności bazy danych (`"pass"` / `"fail"`). |
| `warmup_201` | int | `125` | Liczba pomyślnych odpowiedzi HTTP 201 zarejestrowana w fazie rozgrzewki. |
| `measurement_201` | int | `5432` | Liczba pomyślnych odpowiedzi HTTP 201 zarejestrowana w fazie pomiarowej. |
| `expected_order_rows` | int | `5557` | Oczekiwana liczba wierszy w tabeli `orders` po wykonaniu biegu (warmup + pomiar). |
| `expected_order_item_rows`| int | `16671` | Oczekiwana liczba pozycji w tabeli `order_items` (stosunek 1:1 z payloada). |
| `row_counts` | object | `{...}` | Rzeczywista liczba wierszy w kluczowych tabelach bazy danych odczytana po zakończeniu biegu. |

---

## 4. Formaty Danych Przetworzonych (Pipeline Analityczny)

Pliki generowane przez skrypt [`benchmark/scripts/summarize.py`](file:///home/user/projekty/badanie/benchmark/scripts/summarize.py) w katalogu każdego scenariusza (`results/<scenario>/`).

### Tabela pojedynczych powtórzeń: `runs.csv`

Zawiera znormalizowane metryki wyliczone dla każdego powtórzenia ($n = 1..10$), każdego badanego punktu końcowego i każdego poziomu współbieżności. Dane obejmują wyłącznie stabilne okno pomiarowe (*steady-state* po odrzuceniu pierwszych 10 sekund ramp-upu).

| Nazwa kolumny | Typ | Jednostka | Opis i sposób wyznaczenia |
| :--- | :--- | :--- | :--- |
| `scenario` | string | - | Identyfikator scenariusza (`s1`, `s2`, `s2-pool1`, `s3`). |
| `mode` | string | - | Tryb testu (`single` dla testów izolowanych endpointów, `mixed` dla wielowątkowych). |
| `framework` | string | - | Badana technologia (`laravel` lub `nestjs`). |
| `endpoint` | string | - | Etykieta punktu końcowego (`EP1` .. `EP10`). |
| `users` | int | - | Liczba wirtualnych użytkowników VU. |
| `repetition` | int | - | Numer powtórzenia ($1..10$). |
| `samples` | int | - | Liczba zarejestrowanych zapytań w oknie stabilnym. |
| `window_s` | float | sekundy | Rzeczywisty czas trwania analizowanego okna pomiarowego. |
| `p50_ms` | int / float| ms | Mediana czasu odpowiedzi (50. percentyl) wyznaczona metodą nearest-rank. |
| `mean_ms` | float | ms | Średnia arytmetyczna czasów odpowiedzi w oknie. |
| `p95_ms` | int / float| ms | 95. percentyl czasu odpowiedzi (kluczowa metryka jakościowa SLA). |
| `p99_ms` | int / float| ms | 99. percentyl czasu odpowiedzi (analiza ogona rozkładu opóźnień). |
| `throughput_rps` | float | req/s | Rzeczywista przepustowość: $\text{RPS} = \text{liczba sukcesów} / \text{window\_s}$. |
| `error_rate_pct` | float | % | Odsetek żądań zakończonych błędem HTTP lub przekroczeniem limitu czasu: $100 \times \frac{\text{błędy}}{\text{próbki}}$. |
| `little_ms` | float | ms | Teoretyczny średni czas odpowiedzi wyznaczony z Prawa Little'a: $R = \frac{N}{X} \times 1000$. Omija błąd dyskretyzacji 1 ms JMetera. |
| `cpu_per_request_ms` | float | ms CPU | Średni koszt procesora przypadający na jedno obsłużone żądanie: $\frac{\text{app\_cpu\_mean}}{100} \times \frac{1000}{\text{RPS}}$. |
| `app_cpu_mean` | float | % | Średnie zużycie procesora kontenera aplikacji w oknie pomiarowym (skala 100% = 1 vCPU). |
| `app_cpu_peak` | float | % | Szczytowe chwilowe zużycie procesora kontenera aplikacji. |
| `app_cpu_share_pct`| float | ułamek (0..1)| Udział obciążenia w całym budżecie CPU kontenera: $\frac{\text{app\_cpu\_mean}}{100 \times \text{cpus}}$. |
| `app_mem_mean_mib` | float | MiB | Średnie zużycie pamięci RAM kontenera aplikacji w MiB. |
| `app_mem_peak_mib` | float | MiB | Maksymalne zarejestrowane zużycie pamięci RAM kontenera aplikacji w MiB. |
| `postgres_cpu_mean`| float | % | Średnie zużycie procesora kontenera PostgreSQL. |
| `postgres_cpu_peak`| float | % | Szczytowe zużycie procesora kontenera PostgreSQL. |
| `postgres_cpu_share_pct`| float | ułamek (0..1)| Udział obciążenia w budżecie CPU bazy danych: $\frac{\text{postgres\_cpu\_mean}}{100 \times \text{pg\_cpus}}$. |
| `postgres_mem_mean_mib`| float| MiB | Średnie zużycie pamięci RAM serwera PostgreSQL. |
| `postgres_mem_peak_mib`| float| MiB | Maksymalne zużycie pamięci RAM serwera PostgreSQL. |
| `nginx_cpu_mean` | float | % | Średnie obciążenie CPU serwera reverse proxy Nginx. |
| `nginx_cpu_peak` | float | % | Szczytowe obciążenie CPU serwera Nginx. |
| `nginx_mem_mean_mib`| float | MiB | Średnie zużycie RAM przez serwer Nginx. |
| `nginx_mem_peak_mib`| float | MiB | Maksymalne zużycie RAM przez serwer Nginx. |
| `jmeter_cpu_mean`| float | % | Średnie zużycie procesora generatora JMeter (weryfikacja czy generator nie był wąskim gardłem). |
| `jmeter_cpu_peak`| float | % | Szczytowe zużycie procesora generatora JMeter. |
| `interleave_seed`| int | - | Ziarno użyte do pseudolosowego tasowania frameworków w danym biegu. |
| `framework_order`| string | - | Rzeczywista kolejność uruchomienia frameworków (`laravel nestjs` lub `nestjs laravel`). |
| `orders_count` | int | - | Liczba wierszy w tabeli `orders` po wykonaniu biegu (bramka spójności EP7). |
| `order_items_count`| int | - | Liczba wierszy w tabeli `order_items` po wykonaniu biegu. |
| `reservations_count`| int | - | Liczba wierszy w tabeli `reservations` po wykonaniu biegu (bramka EP9). |

---

### Tabela zbiorcza i agregacje statystyczne: `summary.csv`

Zawiera zsyntetyzowane statystyki ze wszystkich $n = 10$ powtórzeń dla każdego unikalnego układu eksperymentalnego. Dla każdej metryki numerycznej wyznaczana jest **mediana** (jako miara tendencji centralnej odporna na obserwacje odstające) oraz **odchylenie standardowe** (jako miara stabilności i powtarzalności środowiska).

#### Klucze grupujące w `summary.csv`:
- `scenario`: Identyfikator scenariusza (`s1`, `s2`, `s2-pool1`, `s3`).
- `mode`: Tryb badania (`single`, `mixed`).
- `framework`: Nazwa technologii (`laravel`, `nestjs`).
- `endpoint`: Badany punkt końcowy (`EP1` .. `EP10`).
- `users`: Poziom współbieżności wirtualnych użytkowników VU.
- `repetitions`: Liczba uwzględnionych udanych powtórzeń (nominalnie $10$).

#### Zestawienie zagregowanych par metryk (`*_median`, `*_sd`):

| Rodzina metryk | Nazwy kolumn w pliku `summary.csv` | Jednostka | Znaczenie naukowe |
| :--- | :--- | :--- | :--- |
| **Opóźnienia odpowiedzi** | `p50_ms_median`, `p50_ms_sd`<br>`mean_ms_median`, `mean_ms_sd`<br>`p95_ms_median`, `p95_ms_sd`<br>`p99_ms_median`, `p99_ms_sd` | ms | Podstawa weryfikacji hipotez H1, H2 i H3. Miara opóźnienia i stabilności ogona rozkładu SLA. |
| **Opóźnienie ciągłe** | `little_ms_median`, `little_ms_sd` | ms | Estymacja czasu przebywania w systemie wg Prawa Little'a ($R \approx N/X$). |
| **Przepustowość** | `throughput_rps_median`, `throughput_rps_sd` | req/s | Wydajność przetwarzania; weryfikacja liniowości skalowania w warunkach niskiego obciążenia. |
| **Niezawodność** | `error_rate_pct_median`, `error_rate_pct_sd` | % | Wskaźnik błędów HTTP/timeoutów; warunek wstępny ważności testu ($< 1.0\%$). |
| **Koszt obliczeniowy**| `cpu_per_request_ms_median`, `cpu_per_request_ms_sd` | ms CPU | Zużycie czasu procesora na obsługę 1 żądania (efektywność kodu niezależna od kolejkowania). |
| **Zasoby aplikacji** | `app_cpu_mean_median`, `app_cpu_mean_sd`<br>`app_cpu_peak_median`, `app_cpu_peak_sd`<br>`app_cpu_share_pct_median`, `app_cpu_share_pct_sd`<br>`app_mem_mean_mib_median`, `app_mem_mean_mib_sd`<br>`app_mem_peak_mib_median`, `app_mem_peak_mib_sd` | % / MiB | Narzut frameworka na zasoby serwera; weryfikacja reguły CPU $< 80\%$ (Low-Load Validity Rule). |
| **Zasoby bazy danych**| `postgres_cpu_mean_median`, `postgres_cpu_mean_sd`<br>`postgres_cpu_peak_median`, `postgres_cpu_peak_sd`<br>`postgres_cpu_share_pct_median`, `postgres_cpu_share_pct_sd`<br>`postgres_mem_mean_mib_median`, `postgres_mem_mean_mib_sd`<br>`postgres_mem_peak_mib_median`, `postgres_mem_peak_mib_sd` | % / MiB | Obciążenie bazy PostgreSQL; gwarancja braku saturacji warstwy persystencji. |
| **Zasoby proxy Nginx**| `nginx_cpu_mean_median`, `nginx_cpu_mean_sd`<br>`nginx_mem_mean_mib_median`, `nginx_mem_mean_mib_sd` | % / MiB | Weryfikacja transparentności warstwy reverse proxy. |

---

## 5. Pliki Pomocnicze i Diagnostyczne

### Parametry wejściowe JMeter

Pliki generowane automatycznie przez skrypt [`benchmark/scripts/jmeter-data.sh`](file:///home/user/projekty/badanie/benchmark/scripts/jmeter-data.sh) z aktualnego stanu bazy danych i umieszczane w katalogu [`benchmark/jmeter/data/`](file:///home/user/projekty/badanie/benchmark/jmeter/data/):

1. **`ranges.properties`:**
   Zawiera granice kluczy głównych oraz maksymalne numery stron dla zapytań z losowymi parametrami, co eliminuje błędy `404 Not Found` w trakcie testów:
   ```properties
   orders.max=10000
   dishes.max=120
   tables.max=30
   menu_items.pages.max=12
   orders.pages.max=1000
   ```
2. **`available_menu_items.csv`:**
   Lista identyfikatorów dań (`dish_id`), dla których flaga `is_available = true`. Używana przez generator obciążenia w planie EP7 (`POST /orders`), aby symulować wyłącznie poprawne pozycje menu podlegające zamówieniu.

---

### Raporty inspekcji ORM

Pliki diagnostyczne generowane podczas testów dymnych (*smoke tests*) weryfikujące poprawność i symetrię zapytań SQL generowanych przez frameworki:

1. **`results/smoke/sql-compare-<framework>.txt`:**
   Generowany przez [`benchmark/scripts/sql-compare.sh`](file:///home/user/projekty/badanie/benchmark/scripts/sql-compare.sh). Raportuje zrzut z widoku `pg_stat_statements` dla każdego endpointu (liczba wywołań zapytań, całkowity czas wykonania, średni czas na zapytanie).
2. **`results/s3/query-count-<framework>.txt`:**
   Generowany przez [`benchmark/scripts/query-count.sh`](file:///home/user/projekty/badanie/benchmark/scripts/query-count.sh). Zawiera zestawienie wartości nagłówka `X-Query-Count` zwracanego przez mechanizmy profilujące aplikacji w scenariuszu S3, weryfikując wyeliminowanie problemu N+1 zapytań w obu implementacjach.
