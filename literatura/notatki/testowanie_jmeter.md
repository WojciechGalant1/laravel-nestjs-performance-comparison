# Testy obciążeniowe JMeter (scenariusze S1, S2 i S3)

Pomiary wykonuje JMeter 5.6.3 uruchamiany w kontenerze Docker, w tej samej sieci Compose co aplikacje. Kontener nie ma limitów CPU ani pamięci, więc korzysta z rdzeni hosta spoza budżetu aplikacji (4 CPU / 2 GB). Ruch idzie bezpośrednio do `laravel-nginx:80` albo `nestjs-nginx:80`, z pominięciem przekierowania portów Docker Desktop i WSL. JMeter GUI na Windowsie służy tylko do podglądu i edycji planów `.jmx`, nie do pomiarów.

Wszystkie polecenia uruchamiaj w terminalu WSL, w katalogu `benchmark`. Wymagania i przygotowanie bazy opisuje [testowanie_docker.md](testowanie_docker.md).

## 1. Pliki

| Plik | Rola |
|------|------|
| `jmeter/Dockerfile` | obraz z JMeter 5.6.3 (suma SHA-512 sprawdzana przy budowaniu) |
| `jmeter/s1.jmx` | plan S1: logowanie w setUp, EP1, EP2, EP8, tryb `MIXED` |
| `jmeter/s2.jmx` | plan S2: EP3 (200), EP7 i EP9 (201), tryb `MIXED`; EP9 liczy unikalny slot w Groovy z cache kompilacji |
| `jmeter/s3.jmx` | plan S3: EP4, EP5, EP6 (wszystkie GET, HTTP 200), tryb `MIXED`; bez nagłówka `X-Debug-Queries` |
| `scripts/query-count.sh` | jedno żądanie EP4/EP5/EP6 z `X-Debug-Queries`, poza pomiarem |
| `jmeter/run.properties` | format JTL i ustawienia klienta HTTP, wspólne dla obu frameworków |
| `jmeter/data/` | dane wejściowe generowane z bazy (`ranges.properties`, `available_menu_items.csv`) |
| `scripts/jmeter-data.sh` | generuje `jmeter/data/` |
| `scripts/run-scenario.sh` | seria pomiarów: reset, rozgrzewka, pomiar, `docker stats`, `meta.json` |
| `scripts/summarize.py` | percentyle, przepustowość, błędy, CPU/RAM, mediany i tabela H1 |

## 2. Przygotowanie (jednorazowo)

Po `scripts/db-setup.sh` (i po każdej zmianie seedera) wygeneruj dane wejściowe:

```bash
./scripts/jmeter-data.sh
```

Skrypt czyta `laravel_app_template`, zapisuje liczbę stron EP1 i EP2 oraz najwyższe `orders.id` do `jmeter/data/ranges.properties`, a listę dostępnych pozycji menu do `available_menu_items.csv`. Kończy się błędem, jeśli identyfikatory zamówień mają luki, bo EP8 losuje identyfikator z zakresu `1..orders.max`.

Obraz JMetera buduje się przy pierwszym uruchomieniu runnera. Ręcznie:

```bash
docker compose --profile loadtest build jmeter
```

## 3. Pomiar

Uruchomiony może być tylko mierzony stos. Runner odmawia startu, jeśli działa drugi:

```bash
docker compose up -d --wait postgres
./scripts/run-scenario.sh both s1
```

Dla jednego stosu (wznowienie, przebieg kontrolny): `run-scenario.sh laravel s1` albo `nestjs s1`. Seria właściwa przeplata frameworki: `run-scenario.sh both s1`.

Parametry podaje się zmiennymi środowiskowymi. Wartości domyślne odpowiadają metodyce (dla S2 inne są `ENDPOINTS` i `USERS`, patrz niżej):

| Zmienna | Domyślnie (S1) | Znaczenie |
|---------|----------------|-----------|
| `MODE` | `isolated` | `isolated`: osobny przebieg dla każdego endpointu; `mixed`: jeden przebieg z losowym wyborem endpointów planu |
| `ENDPOINTS` | `EP1 EP2 EP8` | endpointy w trybie `isolated` (`PING` jest diagnostyczny i nie wchodzi do H1) |
| `USERS` | `1 2 4 10` | poziomy współbieżności (VU) |
| `REPS` | `10` | powtórzenia |
| `WARMUP` | `120` | rozgrzewka w sekundach (wynik odrzucany) |
| `DURATION` | `180` | pomiar w sekundach |
| `RAMPUP` | `10` | narastanie liczby wątków (wycinane z wyników) |
| `INTERLEAVE_SEED` | `20261002` | ziarno kolejności Laravel/NestJS w trybie `both` |

Każde powtórzenie: `scripts/db-reset.sh` (baza z szablonu i restart aplikacji), rozgrzewka, pomiar ze zbieraniem `docker stats` (aplikacja, nginx, postgres, JMeter), zapis `meta.json`. Pełny S1 `isolated` to 3 endpointy × 4 poziomy VU × 10 powtórzeń × 2 frameworki, przy około 5,5 minuty na przebieg. Werdykt H1 liczy się tylko na poziomach, które przejdą regułę niskiego obciążenia (skalowanie ≥ 0,80 i CPU aplikacji < 80% limitu).

Przerwaną serię wznawia się tym samym poleceniem: powtórzenia z `"status": "complete"` w `meta.json` są pomijane. Jeśli taki przebieg ma inne `WARMUP`/`DURATION`/`RAMPUP` albo inną pulę połączeń NestJS (np. pozostał po teście dymnym), runner przerywa pracę – katalog trzeba przenieść (wyniki testu dymnego są w `results/smoke/`). Nieudany przebieg (np. odrzucone logowanie) zatrzymuje runner i zostaje oznaczony jako `failed`.

Szybki test dymny:

```bash
REPS=1 WARMUP=10 DURATION=20 USERS=10 ./scripts/run-scenario.sh laravel s1
```

### Scenariusz S2

```bash
./scripts/run-scenario.sh laravel s2
```

Domyślnie `ENDPOINTS="EP3 EP7 EP9"` i `USERS="10 50 100 200 500 1000"`. Pełna seria `isolated` to 3 endpointy × 6 poziomów VU × 10 powtórzeń × około 5,5 minuty, czyli około 16,5 godziny na framework. `DURATION=300` wydłuża pomiar do 5 minut, zgodnie z zakresem 3–5 minut z metodyki.

EP3 oczekuje HTTP 200, EP7 i EP9 oczekują HTTP 201. Każde inne kod, w tym kolizja rezerwacji 409 i błąd walidacji 422, liczy się jako błąd. EP7 bierze identyfikator pozycji menu z `available_menu_items.csv` (jedna sztuka, losowy stolik). EP9 buduje termin w preprocesorze Groovy z włączonym cache kompilacji: 200 stolików × 48 slotów po 30 minut, od dnia zapisanego w `ep9.start`. Runner nadpisuje tę datę przy starcie (dzień po ostatniej zaseedowanej rezerwacji, albo dzisiaj, gdy ten dzień już minął) i podaje inny `ep9.offset` dla rozgrzewki (0) i pomiaru (100000000), żeby oba przebiegi nie weszły w te same terminy.

Przebieg kontrolny H2, z jedną pulą połączeń na worker NestJS:

```bash
DB_POOL_SIZE=1 ./scripts/run-scenario.sh nestjs s2
```

Wyniki trafiają do `results/s2-pool1/`, a nie do `results/s2/`. Kolejny start bez tej zmiennej przywraca pulę 10. Sterta JMetera to `-Xms2g -Xmx4g`, żeby 1000 wątków nie spędzało pomiaru w pauzach GC.

### Scenariusz S3

```bash
./scripts/run-scenario.sh both s3
```

Domyślnie `ENDPOINTS="EP1 EP4 EP5 EP6"` i `USERS="1 2 4 10"`. EP1 jest bazą H3 w tym samym scenariuszu. Po S1, zanim ruszy S3: `python3 scripts/summarize.py --freeze-h3-threshold` zapisuje `results/h3_threshold.json`. Podsumowanie S3 bez tego pliku kończy się błędem. EP4 losuje istniejące zamówienie (`1..orders.max`), EP5 losuje danie (`1..dishes.max`), EP6 woła `GET /api/dashboard/summary` bez parametrów. Wszystkie cztery kończą się HTTP 200.

Licznik zapytań SQL nie wchodzi do planu JMetera. Jedno żądanie na endpoint, ze stosem już uruchomionym:

```bash
./scripts/query-count.sh laravel
```

Skrypt loguje się jako manager i wypisuje `X-Query-Count` dla EP4, EP5 i EP6. Zapis jest w `results/s3/query-count-<framework>.txt`.

## 4. Wyniki

```text
results/<scenariusz>/<framework>/<endpoint>/vu<N>/rep<NN>/
    results.jtl   próbki JMetera (CSV)
    stats.csv     docker stats: aplikacja, nginx, postgres (co ok. 0,5 s)
    meta.json     parametry, okno pomiaru, limity kontenera, DB_POOL_SIZE, obraz aplikacji
    jmeter.log, warmup.log
```

W trybie `mixed` katalog endpointu nazywa się `MIXED`, a wyniki są rozdzielane po etykietach samplerów.

Podsumowanie:

```bash
python3 scripts/summarize.py s1
python3 scripts/summarize.py s2
python3 scripts/summarize.py s3
```

Dla S3 skrypt drukuje tabelę H3: D_k = (p95_L(k) − p95_N(k)) − (p95_L(EP1) − p95_N(EP1)) z bootstrapowym CI, próg Y z `results/h3_threshold.json`, werdykt na najwyższym poziomie niskiego obciążenia S3. Licznik SQL pochodzi z `query-count-*.txt` i nie wchodzi do D_k. Dla S2 skrypt drukuje tabelę H2: p95, p99 i odsetek błędów per endpoint i VU oraz próg nasycenia (pierwszy VU z błędem powyżej 5%, albo „brak”). Werdykt bierze nachylenie p95 tylko z poziomów VU ≥ 200 leżących poniżej wcześniejszego z dwóch progów nasycenia (te same punkty po obu stronach; poniżej dwóch punktów „n/d”), mniejszy błąd NestJS przy VU ≥ 500 i wyższy próg nasycenia NestJS. Nachylenie na pełnym zakresie jest drukowane obok i nie rozstrzyga hipotezy. p99 jest w tabeli i nie wchodzi do nachylenia. Przebieg kontrolny podsumowuje się osobno: `python3 scripts/summarize.py s2-pool1`.

Skrypt zapisuje `results/<scenariusz>/runs.csv` (wiersz na powtórzenie i endpoint) oraz `results/<scenariusz>/summary.csv` (mediana i odchylenie standardowe z powtórzeń). Dla S1 drukuje zestaw niskiego obciążenia oraz tabelę H1 z bootstrapowym CI |Δp95|.

Zasady liczenia:
- Okno pomiaru zaczyna się `RAMPUP` sekund po pierwszej próbce.
- Percentyle są liczone metodą najbliższej rangi.
- Przepustowość liczy tylko udane żądania.
- Błąd to odpowiedź inna niż kod sukcesu endpointu (200 dla odczytów i EP8, 201 dla EP7 i EP9) albo timeout po 30 s.
- CPU i RAM pochodzą z próbek `docker stats` przyciętych do tego samego okna. Runner zapisuje różnicę zegara WSL i maszyny wirtualnej Docker Desktop (`clock_offset_s`), bo JMeter i `docker stats` mierzą czas różnymi zegarami.

## 5. Podgląd planu w JMeter GUI (Windows)

1. Zainstaluj Javę 17 lub 21 (np. Eclipse Temurin) i rozpakuj [JMeter 5.6.3](https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.zip). Wersja musi być ta sama co w obrazie.
2. Uruchom `bin\jmeter.bat` i otwórz plan z WSL: `\\wsl$\Ubuntu-22.04\home\wojtek\projekty\badanie\benchmark\jmeter\s1.jmx` (albo `s2.jmx`, `s3.jmx`).
3. Domyślne właściwości planu kierują ruch na `localhost:8080` (Laravel przez Docker Desktop), endpoint `EP1` i 10 wątków. Inny cel ustawisz w `bin\user.properties` albo przy starcie, np. `jmeter.bat -Jport=8081 -Jendpoint=EP8`.
4. Do podglądu odpowiedzi dodaj tymczasowo listener *View Results Tree*, ale nie zapisuj go w pliku: listenery w GUI obciążają generator i nie są częścią planu pomiarowego.

Po edycji w GUI sprawdź `git diff` pliku `.jmx`. GUI zapisuje cały plik od nowa, więc łatwo przypadkiem zmienić np. liczbę wątków na stałą wartość zamiast `${__P(users,10)}`.
