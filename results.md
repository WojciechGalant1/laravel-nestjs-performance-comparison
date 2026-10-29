# Wyniki badań poza artykułem (Rozszerzona seria główna, analizy wrażliwości, profilowanie SQL oraz badania pilotażowe)

## Spis treści
1. [Seria główna ($n = 10$) – poziomy obserwacyjne i nasycenia wykluczone z tabel artykułu](#1-seria-główna-n--10--poziomy-obserwacyjne-i-nasycenia-wykluczone-z-tabel-artykułu)
   - 1.1. Scenariusz S1: Faza nasycenia przy 4 VU oraz 10 VU (EP1, EP5)
   - 1.2. Scenariusz S3: Faza nasycenia przy 4 VU oraz 10 VU (EP1, EP2, EP4, EP6)
   - 1.3. Scenariusz S3: Wpływ zmiany punktu odniesienia (`EP1` vs `EP2b`) na estymator Difference-in-Differences ($D_k$)
2. [Seria główna ($n = 10$) – pełne rozkłady opóźnień ($p_{50}$, Mean, $p_{99}$, Prawo Little'a) oraz telemetria Nginx, JMeter i RAM](#2-seria-główna-n--10--pełne-rozkłady-opóźnień-p_50-mean-p_99-prawo-littlea-oraz-telemetria-nginx-jmeter-i-ram)
   - 2.1. Pełne metryki rozkładu czasu odpowiedzi i odchylenia standardowe (S1, S2, S3)
   - 2.2. Telemetria kontenerów pomocniczych (Nginx, JMeter, RAM PostgreSQL) – dowód braku wąskiego gardła generatora
3. [Eksperymenty wrażliwości i strojenia parametrów (Sensitivity & Parameter Tuning)](#3-eksperymenty-wrażliwości-i-strojenia-parametrów-sensitivity--parameter-tuning)
   - 3.1. Pełna siatka skalowania procesów PHP-FPM (`pm.max_children` $\in \{4, 8, 16, 24, 32, 40\}$) na EP3 i EP7
   - 3.2. Pełna analiza wrażliwości puli połączeń NestJS (`DB_POOL_SIZE = 1` vs `10`, $n = 10$) dla EP3 oraz EP7
4. [Profilowanie warstwy bazodanowej (`pg_stat_statements`) i diagnostyka ścieżki zapisu](#4-profilowanie-warstwy-bazodanowej-pg_stat_statements-i-diagnostyka-ścieżki-zapisu)
   - 4.1. Czas wykonania pojedynczych instrukcji SQL po stronie serwera PostgreSQL (EP1–EP9)
   - 4.2. Diagnostyka asymetrii zapisu w EP8 (`PATCH /api/orders/{id}/status`) – `X-Query-Count` vs `pg_stat_statements`
   - 4.3. Weryfikacja trwałych połączeń PDO (`PDO::ATTR_PERSISTENT`) w Laravelu
5. [Wyniki badań pilotażowych ($n = 1$) i serii eksploracyjnych](#5-wyniki-badań-pilotażowych-n--1-i-serii-eksploracyjnych)
   - 5.1. Pilotaż Scenariusza S1 (EP1, EP2, EP8 przy 1–10 VU) i walidacja reguły niskiego obciążenia
   - 5.2. Pilotaż Scenariusza S2 (EP3, EP7 przy 200–1000 VU) oraz kontrola bramek spójności danych
   - 5.3. Pilotaż Scenariusza S3 (z uwzględnieniem relacji N:M przez tabelę pivot – `EP5: GET /api/dishes/{id}/ingredients`)
   - 5.4. Wczesny pilotaż eksploracyjny (10–1000 VU, `EP9: POST /api/reservations` z indeksem GiST oraz incydent `keepalive_requests`)

---

## 1. Seria główna ($n = 10$) – poziomy obserwacyjne i nasycenia wykluczone z tabel artykułu

Zgodnie z regułą walidacji niskiego obciążenia (*Low-Load Validity Rule*, Sekcja 3.3 metodyki), do formalnego testowania hipotez H1 i H3 zakwalifikowano wyłącznie poziomy 1 VU oraz 2 VU (gdzie średnie użycie CPU kontenerów $< 80\%$ limitu, a skalowanie przepustowości $X(N)/(N \cdot X(1)) \ge 0.80$). Pomiary dla **4 VU** oraz **10 VU** zostały jednak w pełni wykonane w głównej kampanii pomiarowej ($n = 10$ powtórzeń, 180 s pomiaru na przebieg) i stanowią bezpośredni dowód przejścia obu architektur w stan nasycenia CPU oraz kolejkowania.

### 1.1. Scenariusz S1: Faza nasycenia przy 4 VU oraz 10 VU (EP1, EP5)
Źródło danych: `benchmark/results/s1/summary.csv` ($n = 10$, wartości prezentowane jako mediana $\pm$ SD).

| Endpoint | Poziom VU | $p_{50}$ (ms)<br>Laravel / NestJS | Średnia (ms)<br>Laravel / NestJS | $p_{95}$ (ms)<br>Laravel / NestJS | $p_{99}$ (ms)<br>Laravel / NestJS | Przepustowość (RPS)<br>Laravel / NestJS | Stosunek RPS<br>($X_N / X_L$) | App CPU [% limitu]<br>Laravel / NestJS | PG CPU [% limitu]<br>Laravel / NestJS | CPU / req (ms)<br>Laravel / NestJS |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EP1** *(GET /tables)* | **1 VU** *(w artykule)* | 6.0 / 1.0 | 6.53 / 1.20 | 8.0 / 2.0 | 9.5 / 2.0 | 151.2 $\pm$ 13.7 / 806.5 $\pm$ 34.4 | 5.33× | 22.8% / 19.3% | 2.6% / 5.7% | 6.00 / 0.93 |
| | **2 VU** *(w artykule)* | 6.5 / 1.0 | 6.76 / 1.28 | 8.0 / 2.0 | 10.0 / 2.0 | 290.8 $\pm$ 36.1 / 1519.8 $\pm$ 71.0 | 5.23× | 45.4% / 36.9% | 4.8% / 11.1% | 6.20 / 0.96 |
| | **4 VU** *(nasycenie Lar)* | **6.0 / 1.0** | **6.65 / 1.37** | **8.0 / 2.0** | **10.0 / 3.0** | **595.5 $\pm$ 61.9 / 2839.2 $\pm$ 157.8** | **4.77×** | **93.5% / 72.4%** | **10.2% / 21.8%** | **5.93 / 1.01** |
| | **10 VU** *(nasycenie obu)* | **14.5 / 2.0** | **15.38 / 2.66** | **20.0 / 4.0** | **25.0 / 13.0** | **646.6 $\pm$ 53.7 / 3687.2 $\pm$ 192.4** | **5.70×** | **95.7% / 100.2%** | **10.3% / 27.6%** | **5.68 / 1.09** |
| **EP5** *(PATCH status)* | **1 VU** *(w artykule)* | 6.0 / 2.5 | 6.62 / 2.51 | 8.0 / 4.0 | 10.0 / 4.0 | 148.7 $\pm$ 14.3 / 391.7 $\pm$ 13.0 | 2.63× | 19.2% / 12.8% | 2.5% / 5.1% | 5.10 / 1.28 |
| | **2 VU** *(w artykule)* | 6.0 / 3.0 | 6.02 / 2.71 | 8.0 / 4.0 | 9.0 / 5.0 | 328.7 $\pm$ 34.4 / 726.8 $\pm$ 26.8 | 2.21× | 38.7% / 23.7% | 5.1% / 9.6% | 4.72 / 1.33 |
| | **4 VU** *(blisko progu)* | **6.0 / 3.0** | **6.42 / 3.03** | **8.0 / 5.0** | **10.0 / 5.5** | **615.8 $\pm$ 45.2 / 1300.2 $\pm$ 80.7** | **2.11×** | **77.9% / 42.6%** | **10.0% / 17.8%** | **5.05 / 1.34** |
| | **10 VU** *(nasycenie)* | **14.5 / 4.0** | **15.92 / 3.91** | **20.0 / 6.0** | **25.5 / 8.0** | **623.8 $\pm$ 63.3 / 2529.2 $\pm$ 134.8** | **4.05×** | **79.9% / 84.2%** | **10.0% / 36.4%** | **5.08 / 1.34** |


1. **Sztywny sufit przepustowości 4 workerów PHP-FPM:** Na EP1 między 4 VU a 10 VU przepustowość Laravela rośnie zaledwie o $+8.6\%$ ($595.5 \rightarrow 646.6\text{ RPS}$), a na EP5 o $+1.3\%$ ($615.8 \rightarrow 623.8\text{ RPS}$), ponieważ wszystkie 4 procesy robocze PHP-FPM są już zajęte. Dalsze zwiększanie liczby użytkowników z 4 do 10 VU powoduje wyłącznie liniowy wzrost kolejki w gnieździe FastCGI ($p_{95}$ skacze z $8.0\text{ ms}$ do $20.0\text{ ms}$), podczas gdy jednostkowy koszt CPU na żądanie pozostaje niezmienny ($\sim 5.05–5.93\text{ ms}$).
2. **Skalowanie NestJS między 4 a 10 VU:** Na EP5 przy 4 VU NestJS zużywa dopiero $42.6\%$ limitu CPU ($1300.2\text{ RPS}$), dzięki czemu przy przejściu na 10 VU niemal podwaja przepustowość do $2529.2\text{ RPS}$ (przy $84.2\%$ CPU), a opóźnienie $p_{95}$ wzrasta jedynie z $5.0\text{ ms}$ do $6.0\text{ ms}$.

---

### 1.2. Scenariusz S3: Faza nasycenia przy 4 VU oraz 10 VU (EP1, EP2, EP4, EP6)
Źródło danych: `benchmark/results/s3_backup_legacy/summary.csv` ($n = 10$ powtórzeń).

| Endpoint | Poziom VU | $p_{50}$ (ms)<br>Laravel / NestJS | $p_{95}$ (ms)<br>Laravel / NestJS | $p_{99}$ (ms)<br>Laravel / NestJS | Przepustowość (RPS)<br>Laravel / NestJS | App CPU [% limitu]<br>Laravel / NestJS | PG CPU [% limitu]<br>Laravel / NestJS | CPU / req (ms)<br>Laravel / NestJS |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EP1** *(0 rel)* | **4 VU** | 6.0 / 1.0 | 8.5 / 2.0 | 11.0 / 3.0 | 619.2 $\pm$ 36.1 / 2873.0 $\pm$ 103.5 | 88.2% / 69.2% | 9.9% / 21.1% | 5.75 / 0.96 |
| | **10 VU** | 16.0 / 2.0 | 20.5 / 4.0 | 26.5 / 12.0 | 616.5 $\pm$ 43.3 / 3908.7 $\pm$ 109.1 | 90.0% / 99.6% | 9.7% / 27.4% | 5.87 / 1.02 |
| **EP2** *(1 rel)* | **4 VU** | 8.0 / 2.0 | 10.0 / 3.0 | 12.0 / 4.0 | 466.6 $\pm$ 25.0 / 1623.0 $\pm$ 62.6 | 89.6% / 68.6% | 11.7% / 27.6% | 7.62 / 1.69 |
| | **10 VU** | 21.0 / 4.0 | 27.5 / 7.0 | 35.0 / 15.0 | 456.9 $\pm$ 27.0 / 2286.6 $\pm$ 83.2 | 90.9% / 99.8% | 11.6% / 38.6% | 7.87 / 1.75 |
| **EP4** *(3-lvl nested)* | **4 VU** | 9.0 / 3.0 | 11.0 / 4.0 | 13.5 / 5.0 | 430.5 $\pm$ 25.5 / 1339.6 $\pm$ 45.4 | 82.6% / 59.8% | 19.2% / 38.4% | 7.68 / 1.78 |
| | **10 VU** | 22.0 / 5.0 | 30.5 / 7.5 | 37.0 / 12.0 | 424.6 $\pm$ 21.4 / 1956.5 $\pm$ 79.3 | 84.2% / 99.2% | 19.3% / 56.1% | 8.02 / 2.03 |
| **EP6** *(3 JOIN + GROUP BY)* | **1 VU** *(w artykule)* | 112.0 / 108.5 | 134.5 / 126.5 | 158.0 / 152.5 | 8.2 $\pm$ 0.5 / 8.6 $\pm$ 0.6 | 1.2% / 0.6% | 23.7% / 24.4% | 5.83 / 2.75 |
| | **2 VU** *(w artykule)* | 126.0 / 118.5 | 161.0 / 149.5 | 189.0 / 172.0 | 15.8 $\pm$ 0.6 / 16.3 $\pm$ 0.9 | 2.1% / 0.9% | 48.0% / 49.4% | 5.35 / 2.45 |
| | **4 VU** *(nasycenie PG)* | **138.0 / 135.0** | **164.5 / 164.5** | **194.5 / 189.0** | **28.4 $\pm$ 1.2 / 29.3 $\pm$ 0.9** | **4.0% / 1.5%** | **97.7% / 98.8%** | **5.66 / 2.00** |
| | **10 VU** *(degradacja PG)* | **350.0 / 466.5** | **405.5 / 503.0** | **429.0 / 521.5** | **28.5 $\pm$ 1.0 / 21.2 $\pm$ 0.6** | **4.0% / 1.2%** | **97.9% / 97.8%** | **5.55 / 2.38** |

- Przy **4 VU** kontener PostgreSQL osiąga pełne nasycenie procesora w obu technologiach ($97.7\%$ w Laravelu vs $98.8\%$ w NestJS), a opóźnienie ogona $p_{95}$ zrównuje się co do ułamka milisekundy (**$164.5\text{ ms}$ vs $164.5\text{ ms}$**).
- Przy przejściu z **4 VU na 10 VU** w Laravelu (gdzie maksymalnie 4 workery PHP-FPM mogą wysyłać zapytania jednocześnie) przepustowość bazy utrzymuje stabilne plateau **$28.5\text{ RPS}$**, a opóźnienie $p_{95}$ wynosi **$405.5\text{ ms}$** (kolejka oczekuje przed PHP-FPM).
- W NestJS (gdzie 10 wirtualnych użytkowników wpuszcza do bazy 10 równoległych ciężkich zapytań agregujących naraz, przekraczając liczbę 4 rdzeni vCPU PostgreSQL) dochodzi do rywalizacji o zasoby bazy danych: przepustowość **spada z $29.3\text{ RPS}$ do $21.2\text{ RPS}$ ($-27.6\%$)**, a opóźnienie $p_{95}$ rośnie do **$503.0\text{ ms}$** (o $97.5\text{ ms}$ gorzej niż w Laravelu). Stanowi to drugą, całkowicie niezależną weryfikację mechanizmu zaobserwowanego w scenariuszu S2 na EP3!

---

### 1.3. Scenariusz S3: Wpływ zmiany punktu odniesienia (`EP1` vs `EP2b`) na estymator Difference-in-Differences ($D_k$)
W pierwotnej wersji scenariusza S3 (`s3_backup_legacy`) punktem odniesienia (baseline) dla relacji była tabela `tables` (`EP1`, 50 wierszy, brak filtrów `WHERE` i `ORDER BY`). W toku rewizji metodologicznej wprowadzono kontrolę wewnętrzną na tej samej tabeli `menu_items` (`EP2b: GET /api/menu-items?plain=1`, 45 wierszy, te same dwa warunki filtrujące i sortowanie co w `EP2`, ale bez *eager loadingu* `dishes`).

Porównanie obu punktów odniesienia przy $n = 10$:

| Punkt odniesienia (Baseline) | Poziom VU | $p_{95}$ Baseline (ms)<br>Laravel / NestJS | Luka bazowa $S_{\text{base}}$ (ms) | $p_{95}$ EP2 (ms)<br>Laravel / NestJS | Luka $S_{\text{EP2}}$ (ms) | Kontrast $D_{\text{EP2}} = S_{\text{EP2}} - S_{\text{base}}$ | Kontrast ciągły Mean $D_{\text{EP2}}$ | Kontrast ciągły CPU/req $D_{\text{EP2}}$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Legacy: EP1** *(tabela `tables`)* | 1 VU | 7.0 / 2.0 | 5.0 ms | 10.5 / 3.0 | 7.5 ms | **+2.50 ms** | +2.38 ms | +1.76 ms |
| | 2 VU | 7.5 / 2.0 | 5.5 ms | 10.0 / 3.0 | 7.0 ms | **+1.50 ms** | +1.99 ms | +1.85 ms |
| **Aktualny: EP2b** *(ta sama tabela `menu_items`)* | 1 VU | 7.5 / 2.0 | 5.5 ms | 10.5 / 3.0 | 7.5 ms | **+2.00 ms** $[1.00, 3.00]$ | +1.86 ms | +1.19 ms |
| | 2 VU | 7.5 / 2.0 | 5.5 ms | 10.0 / 3.0 | 7.0 ms | **+1.50 ms** $[1.00, 3.00]$ | +1.81 ms | +1.72 ms |

 Zastąpienie `EP1` przez `EP2b` wyeliminowało zmienną zakłócającą (różnicę liczby wierszy, typów kolumn oraz klauzul `WHERE`/`ORDER BY`), korygując kontrast przy 1 VU z $+2.50\text{ ms}$ do $+2.00\text{ ms}$, natomiast na głównym poziomie werdyktowym (2 VU) kontrast punktowy $p_{95}$ okazał się całkowicie odporny i wyniósł dokładnie $+1.50\text{ ms}$ w obu wariantach.

---

## 2. Seria główna ($n = 10$) – pełne rozkłady opóźnień ($p_{50}$, Mean, $p_{99}$, Prawo Little'a) oraz telemetria Nginx, JMeter i RAM

W tabelach artykułu umieszczono wyłącznie medianę $p_{95}$, przepustowość oraz procentowe wykorzystanie CPU aplikacji i bazy danych. Poniżej zestawiono pełne statystyki rozkładu opóźnień (wraz z odchyleniem standardowym SD z 10 powtórzeń) oraz telemetrię wszystkich kontenerów.

### 2.1. Pełne metryki rozkładu czasu odpowiedzi i odchylenia standardowe (S1, S2, S3)

#### Scenariusz S1 ($n = 10$, 1–2 VU):
| Endpoint | VU | Framework | $p_{50} \pm \text{SD}$ (ms) | $\text{Mean} \pm \text{SD}$ (ms) | $p_{95} \pm \text{SD}$ (ms) | $p_{99} \pm \text{SD}$ (ms) | Little's Law $N/X \pm \text{SD}$ (ms) | Throughput $\pm \text{SD}$ (RPS) | CPU/req $\pm \text{SD}$ (ms) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EP1** | 1 | Laravel | 6.0 $\pm$ 0.48 | 6.53 $\pm$ 0.56 | 8.0 $\pm$ 0.70 | 9.5 $\pm$ 1.26 | 6.62 $\pm$ 0.57 | 151.2 $\pm$ 13.7 | 6.00 $\pm$ 0.53 |
| | 1 | NestJS | 1.0 $\pm$ 0.00 | 1.20 $\pm$ 0.05 | 2.0 $\pm$ 0.00 | 2.0 $\pm$ 0.42 | 1.24 $\pm$ 0.05 | 806.5 $\pm$ 34.4 | 0.93 $\pm$ 0.06 |
| | 2 | Laravel | 6.5 $\pm$ 0.85 | 6.76 $\pm$ 0.93 | 8.0 $\pm$ 1.16 | 10.0 $\pm$ 1.49 | 6.88 $\pm$ 0.94 | 290.8 $\pm$ 36.1 | 6.20 $\pm$ 0.82 |
| | 2 | NestJS | 1.0 $\pm$ 0.00 | 1.28 $\pm$ 0.06 | 2.0 $\pm$ 0.00 | 2.0 $\pm$ 0.42 | 1.32 $\pm$ 0.06 | 1519.8 $\pm$ 71.0 | 0.96 $\pm$ 0.05 |
| **EP5** | 1 | Laravel | 6.0 $\pm$ 0.53 | 6.62 $\pm$ 0.65 | 8.0 $\pm$ 0.63 | 10.0 $\pm$ 1.05 | 6.73 $\pm$ 0.65 | 148.7 $\pm$ 14.3 | 5.10 $\pm$ 0.46 |
| | 1 | NestJS | 2.5 $\pm$ 0.53 | 2.51 $\pm$ 0.09 | 4.0 $\pm$ 0.00 | 4.0 $\pm$ 0.32 | 2.55 $\pm$ 0.09 | 391.7 $\pm$ 13.0 | 1.28 $\pm$ 0.05 |
| | 2 | Laravel | 6.0 $\pm$ 0.74 | 6.02 $\pm$ 0.77 | 8.0 $\pm$ 0.99 | 9.0 $\pm$ 1.20 | 6.10 $\pm$ 0.77 | 328.7 $\pm$ 34.4 | 4.72 $\pm$ 0.60 |
| | 2 | NestJS | 3.0 $\pm$ 0.00 | 2.71 $\pm$ 0.10 | 4.0 $\pm$ 0.00 | 5.0 $\pm$ 0.00 | 2.75 $\pm$ 0.10 | 726.8 $\pm$ 26.8 | 1.33 $\pm$ 0.06 |

#### Scenariusz S2 ($n = 10$, 200–1000 VU):
| Endpoint | VU | Framework | $p_{50} \pm \text{SD}$ (ms) | $\text{Mean} \pm \text{SD}$ (ms) | $p_{95} \pm \text{SD}$ (ms) | $p_{99} \pm \text{SD}$ (ms) | Little's Law $N/X \pm \text{SD}$ (ms) | Throughput $\pm \text{SD}$ (RPS) | CPU/req $\pm \text{SD}$ (ms) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EP3** | 200 | Laravel | 1372.0 $\pm$ 53.6 | 1396.3 $\pm$ 50.8 | 1463.0 $\pm$ 50.1 | 1503.0 $\pm$ 54.0 | 1373.0 $\pm$ 50.2 | 145.7 $\pm$ 5.4 | 9.75 $\pm$ 0.37 |
| | 200 | NestJS | 1277.0 $\pm$ 192.4 | 1394.4 $\pm$ 180.7 | 1798.5 $\pm$ 175.4 | 2124.5 $\pm$ 227.6 | 1383.6 $\pm$ 182.8 | 144.6 $\pm$ 19.6 | 3.74 $\pm$ 0.39 |
| | 500 | Laravel | 3425.0 $\pm$ 133.5 | 3432.5 $\pm$ 130.6 | 3497.0 $\pm$ 131.5 | 3538.5 $\pm$ 138.6 | 3439.9 $\pm$ 131.7 | 145.4 $\pm$ 5.6 | 9.81 $\pm$ 0.35 |
| | 500 | NestJS | 3578.0 $\pm$ 459.4 | 3510.7 $\pm$ 430.5 | 4113.0 $\pm$ 404.8 | 4355.0 $\pm$ 405.1 | 3476.3 $\pm$ 433.6 | 143.8 $\pm$ 18.6 | 3.75 $\pm$ 0.37 |
| | 1000 | Laravel | 6838.5 $\pm$ 177.2 | 6846.8 $\pm$ 175.7 | 6903.5 $\pm$ 177.4 | 6948.0 $\pm$ 174.1 | 6868.7 $\pm$ 178.4 | 145.6 $\pm$ 3.8 | 9.80 $\pm$ 0.27 |
| | 1000 | NestJS | 6961.5 $\pm$ 612.8 | 6996.4 $\pm$ 599.2 | 7922.5 $\pm$ 652.0 | 8261.0 $\pm$ 679.2 | 7025.0 $\pm$ 613.2 | 142.3 $\pm$ 12.6 | 3.87 $\pm$ 0.25 |
| **EP7** | 200 | Laravel | 434.0 $\pm$ 14.3 | 440.1 $\pm$ 14.6 | 488.5 $\pm$ 20.6 | 509.5 $\pm$ 23.6 | 441.5 $\pm$ 14.5 | 453.0 $\pm$ 14.9 | 6.13 $\pm$ 0.13 |
| | 200 | NestJS | 88.0 $\pm$ 3.3 | 90.4 $\pm$ 3.6 | 112.0 $\pm$ 5.2 | 126.5 $\pm$ 9.6 | 91.1 $\pm$ 3.6 | 2194.4 $\pm$ 85.4 | 1.81 $\pm$ 0.07 |
| | 500 | Laravel | 1142.0 $\pm$ 124.2 | 1152.9 $\pm$ 128.0 | 1300.5 $\pm$ 304.9 | 1347.5 $\pm$ 375.9 | 1154.7 $\pm$ 125.9 | 433.0 $\pm$ 41.3 | 6.16 $\pm$ 0.15 |
| | 500 | NestJS | 240.0 $\pm$ 8.2 | 241.6 $\pm$ 9.1 | 275.0 $\pm$ 20.2 | 298.5 $\pm$ 34.4 | 244.1 $\pm$ 9.2 | 2048.2 $\pm$ 75.8 | 1.90 $\pm$ 0.06 |
| | 1000 | Laravel | 3319.5 $\pm$ 192.6 | 3349.1 $\pm$ 176.2 | 3647.0 $\pm$ 231.1 | 3756.5 $\pm$ 236.2 | 3492.4 $\pm$ 197.4 | 286.3 $\pm$ 16.5 | 6.06 $\pm$ 0.15 |
| | 1000 | NestJS | 495.0 $\pm$ 21.6 | 499.7 $\pm$ 21.4 | 559.0 $\pm$ 31.1 | 608.0 $\pm$ 47.4 | 506.5 $\pm$ 21.5 | 1974.4 $\pm$ 83.2 | 1.83 $\pm$ 0.05 |

#### Scenariusz S3 ($n = 10$, 1–2 VU):
| Endpoint | VU | Framework | $p_{50} \pm \text{SD}$ (ms) | $\text{Mean} \pm \text{SD}$ (ms) | $p_{95} \pm \text{SD}$ (ms) | $p_{99} \pm \text{SD}$ (ms) | Little's Law $N/X \pm \text{SD}$ (ms) | Throughput $\pm \text{SD}$ (RPS) | CPU/req $\pm \text{SD}$ (ms) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EP2b** | 1 | Laravel | 6.0 $\pm$ 0.00 | 6.21 $\pm$ 0.11 | 7.5 $\pm$ 0.53 | 10.0 $\pm$ 0.52 | 6.30 $\pm$ 0.11 | 158.8 $\pm$ 2.9 | 5.63 $\pm$ 0.11 |
| | 1 | NestJS | 1.0 $\pm$ 0.00 | 1.26 $\pm$ 0.02 | 2.0 $\pm$ 0.00 | 2.0 $\pm$ 0.32 | 1.31 $\pm$ 0.02 | 763.4 $\pm$ 13.7 | 0.90 $\pm$ 0.02 |
| | 2 | Laravel | 6.0 $\pm$ 0.42 | 5.89 $\pm$ 0.34 | 7.5 $\pm$ 0.53 | 9.5 $\pm$ 0.53 | 5.96 $\pm$ 0.34 | 335.4 $\pm$ 19.6 | 5.22 $\pm$ 0.31 |
| | 2 | NestJS | 1.0 $\pm$ 0.00 | 1.27 $\pm$ 0.04 | 2.0 $\pm$ 0.00 | 2.0 $\pm$ 0.32 | 1.31 $\pm$ 0.04 | 1528.4 $\pm$ 45.7 | 0.87 $\pm$ 0.03 |
| **EP2** | 1 | Laravel | 8.5 $\pm$ 0.52 | 8.43 $\pm$ 0.31 | 10.5 $\pm$ 0.53 | 12.0 $\pm$ 0.74 | 8.50 $\pm$ 0.31 | 117.7 $\pm$ 4.3 | 7.46 $\pm$ 0.27 |
| | 1 | NestJS | 2.0 $\pm$ 0.00 | 2.06 $\pm$ 0.10 | 3.0 $\pm$ 0.00 | 4.0 $\pm$ 0.52 | 2.11 $\pm$ 0.10 | 474.0 $\pm$ 21.8 | 1.54 $\pm$ 0.07 |
| | 2 | Laravel | 8.0 $\pm$ 0.48 | 8.47 $\pm$ 0.44 | 10.0 $\pm$ 0.67 | 12.0 $\pm$ 0.79 | 8.54 $\pm$ 0.44 | 234.1 $\pm$ 12.6 | 7.51 $\pm$ 0.40 |
| | 2 | NestJS | 2.0 $\pm$ 0.00 | 2.04 $\pm$ 0.11 | 3.0 $\pm$ 0.00 | 3.5 $\pm$ 0.53 | 2.08 $\pm$ 0.11 | 961.2 $\pm$ 48.9 | 1.44 $\pm$ 0.07 |
| **EP4** | 1 | Laravel | 8.5 $\pm$ 0.53 | 8.72 $\pm$ 0.49 | 10.0 $\pm$ 0.74 | 12.5 $\pm$ 0.85 | 8.81 $\pm$ 0.49 | 113.5 $\pm$ 6.3 | 7.20 $\pm$ 0.41 |
| | 1 | NestJS | 3.0 $\pm$ 0.00 | 2.61 $\pm$ 0.07 | 3.0 $\pm$ 0.42 | 5.0 $\pm$ 0.32 | 2.67 $\pm$ 0.07 | 375.1 $\pm$ 10.2 | 1.71 $\pm$ 0.05 |
| | 2 | Laravel | 9.0 $\pm$ 0.32 | 8.95 $\pm$ 0.48 | 10.5 $\pm$ 0.70 | 13.0 $\pm$ 0.95 | 9.05 $\pm$ 0.48 | 220.9 $\pm$ 11.4 | 7.47 $\pm$ 0.40 |
| | 2 | NestJS | 3.0 $\pm$ 0.00 | 2.82 $\pm$ 0.10 | 4.0 $\pm$ 0.00 | 5.0 $\pm$ 0.42 | 2.88 $\pm$ 0.10 | 694.4 $\pm$ 23.2 | 1.76 $\pm$ 0.06 |
| **EP6** | 1 | Laravel | 112.0 $\pm$ 6.6 | 113.9 $\pm$ 6.8 | 134.5 $\pm$ 8.9 | 158.0 $\pm$ 10.6 | 121.4 $\pm$ 6.9 | 8.2 $\pm$ 0.5 | 5.83 $\pm$ 0.41 |
| | 1 | NestJS | 108.5 $\pm$ 7.3 | 110.2 $\pm$ 7.4 | 126.5 $\pm$ 8.3 | 152.5 $\pm$ 12.2 | 116.5 $\pm$ 7.4 | 8.6 $\pm$ 0.6 | 2.75 $\pm$ 0.25 |
| | 2 | Laravel | 126.0 $\pm$ 5.2 | 127.8 $\pm$ 5.1 | 161.0 $\pm$ 8.1 | 189.0 $\pm$ 9.6 | 126.7 $\pm$ 5.1 | 15.8 $\pm$ 0.6 | 5.35 $\pm$ 0.30 |
| | 2 | NestJS | 118.5 $\pm$ 6.9 | 120.2 $\pm$ 6.9 | 149.5 $\pm$ 8.7 | 172.0 $\pm$ 9.3 | 122.4 $\pm$ 6.8 | 16.3 $\pm$ 0.9 | 2.45 $\pm$ 0.15 |

---

### 2.2. Telemetria kontenerów pomocniczych (Nginx, JMeter, RAM PostgreSQL) – dowód braku wąskiego gardła generatora

Reverse proxy (Nginx, limit 1 vCPU = 100% oraz 256 MiB RAM), ani generator obciążenia (Apache JMeter, brak limitu na hoście 16 vCPU = 1600%) nie stanowiły wąskiego gardła pomiarowego w żadnym scenariuszu:

| Scenariusz / Endpoint | Poziom VU | Nginx CPU Mean (%)<br>Laravel / NestJS | Nginx RAM Mean (MiB)<br>Laravel / NestJS | PG RAM Mean (MiB)<br>Laravel / NestJS | JMeter CPU Mean (%)<br>Laravel / NestJS | JMeter RAM Peak (MiB)<br>Laravel / NestJS |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **S1: EP1** | 2 VU | 10.7% / 21.8% | 10.7 / 11.4 | 382.9 / 382.4 | 10.9% / 22.8% | 1325.1 / 1452.0 |
| **S1: EP1** | 10 VU | 21.2% / 51.3% | 11.4 / 12.2 | 383.5 / 401.2 | 18.0% / 50.8% | 1445.9 / 1486.8 |
| **S2: EP3** | 200 VU | 5.6% / 3.7% | 14.0 / 13.8 | 387.5 / 451.7 | 11.1% / 10.4% | 551.4 / 587.6 |
| **S2: EP3** | 1000 VU | 5.9% / 3.9% | 26.2 / 26.0 | 389.0 / 463.8 | 11.2% / 10.9% | 697.8 / 767.4 |
| **S2: EP7** | 200 VU | 14.2% / 33.4% | 14.1 / 13.9 | 406.5 / 485.0 | 14.8% / 36.1% | 1447.9 / 1692.7 |
| **S2: EP7** | 1000 VU | 9.0% / 31.3% | 26.1 / 26.1 | 409.5 / 512.0 | 13.7% / 35.6% | 1459.2 / 1916.9 |
| **S3: EP2** | 2 VU | 9.1% / 14.4% | 10.8 / 11.3 | 382.4 / 382.4 | 9.8% / 17.5% | 540.6 / 1444.9 |
| **S3: EP4** | 2 VU | 8.2% / 10.2% | 10.7 / 11.0 | 382.1 / 383.1 | 9.2% / 12.9% | 465.2 / 1221.6 |
| **S3: EP6** | 2 VU | 0.9% / 0.8% | 10.6 / 10.8 | 396.3 / 390.2 | 2.6% / 2.7% | 288.0 / 285.8 |

- Zużycie CPU przez kontener **Nginx** w testach werdyktowych nie przekroczyło $33.4\%$ pojedynczego rdzenia vCPU (i max $51.3\%$ przy 10 VU na EP1), a zużycie pamięci RAM wzrosło z $\sim 10.7\text{ MiB}$ (1–2 VU) do $\sim 26.2\text{ MiB}$ (1000 VU).
- Kontener **JMetera** zużywał średnio jedynie $2.6\%–36.1\%$ pojedynczego rdzenia (na maszynie posiadającej 16 wątków logicznych, tj. $< 2.5\%$ całkowitej mocy obliczeniowej hosta), co jednoznacznie wyklucza nasycenie generatora obciążenia.

---

## 3. Eksperymenty wrażliwości i strojenia parametrów (Sensitivity & Parameter Tuning)

### 3.1. Pełna siatka skalowania procesów PHP-FPM (`pm.max_children` $\in \{4, 8, 16, 24, 32, 40\}$) na EP3 i EP7

W artykule w Sekcji 4.2 wspomniano jedynie skrótowo o punktach `pm.max_children = 8` oraz `pm.max_children = 40`. Poniżej znajduje się **pełna tabela 24 przebiegów eksploracyjnych** (`benchmark/results/smoke/s2-fpm-pilot/summary.csv`) obrazująca klasyczną krzywą skalowalności (Universal Scalability Law) z trzema fazami: *niedosyceniem (4 workery)*, *punktem optymalnym (8 workerów = $2 \times \text{vCPU}$)* oraz *degradacją przez przełączanie kontekstu i dławienie bazy danych (16–40 workerów)*.

| Endpoint | Poziom VU | Liczba workerów PHP-FPM (`pm.max_children`) | $p_{50}$ (ms) | Średnia (ms) | $p_{95}$ (ms) | $p_{99}$ (ms) | Przepustowość (RPS) | App CPU Mean [% limitu 4 vCPU] | PG CPU Mean [% limitu 4 vCPU] | App RAM Mean / Peak (MiB) | PG RAM Mean (MiB) | CPU / req (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EP3** *(Read)* | **500 VU** | **4** *(domyślny)* | 3504 | 3516.8 | **3750** | 3802 | **138.9** | 34.4% (137.4%) | 61.9% (247.5%) | 52.0 / 52.4 | 385.5 | 9.89 |
| | | **8** *(optimum)* | 3082 | 3129.6 | **3558** | 3737 | **154.0** | 37.9% (151.7%) | 97.6% (390.4%) | 66.2 / 66.5 | 389.0 | 9.85 |
| | | **16** | 3418 | 3473.8 | **4001** | 4099 | **136.4** | 34.5% (137.8%) | 99.1% (396.3%) | 97.8 / 98.4 | 396.9 | 10.10 |
| | | **24** | 3592 | 3704.9 | **4580** | 4769 | **124.2** | 32.1% (128.5%) | 99.2% (396.8%) | 133.2 / 133.9 | 405.5 | 10.35 |
| | | **32** | 3655 | 3800.7 | **4856** | 5018 | **122.4** | 30.8% (123.3%) | 99.1% (396.4%) | 168.1 / 169.3 | 413.1 | 10.08 |
| | | **40** *(dławienie PG)* | 3741 | 3868.5 | **5259** | 5610 | **118.4** | 29.8% (119.3%) | 99.1% (396.5%) | 202.8 / 203.9 | 419.6 | 10.07 |
| **EP3** *(Read)* | **1000 VU** | **4** *(domyślny)* | 7301 | 7265.1 | **7645** | 7697 | **135.6** | 33.4% (133.5%) | 62.2% (248.6%) | 52.0 / 52.3 | 385.6 | 9.84 |
| | | **8** *(optimum)* | 6017 | 5995.7 | **6222** | 6291 | **161.4** | 40.3% (161.1%) | 98.0% (392.0%) | 66.2 / 66.6 | 389.1 | 9.98 |
| | | **16** | 6741 | 6724.4 | **7247** | 7384 | **141.7** | 35.4% (141.4%) | 99.2% (396.8%) | 98.3 / 98.8 | 397.0 | 9.98 |
| | | **24** | 6937 | 7089.3 | **8542** | 8868 | **129.0** | 33.0% (131.9%) | 99.3% (397.2%) | 133.1 / 133.9 | 404.9 | 10.22 |
| | | **32** | 7119 | 7329.8 | **9224** | 9644 | **123.3** | 31.1% (124.5%) | 99.1% (396.6%) | 168.4 / 169.3 | 413.1 | 10.10 |
| | | **40** *(dławienie PG)* | 7491 | 7671.5 | **10075** | 10548 | **117.2** | 29.9% (119.7%) | 99.3% (397.4%) | 202.9 / 203.9 | 419.6 | 10.21 |
| **EP7** *(Write)* | **500 VU** | **4** *(domyślny)* | 1221 | 1225.7 | **1362** | 1409 | **405.8** | 63.6% (254.3%) | 16.3% (65.4%) | 52.8 / 53.3 | 405.6 | 6.27 |
| | | **8** *(sufit CPU)* | 972 | 983.7 | **1166** | 1225 | **507.6** | **99.9% (399.8%)** | 22.8% (91.1%) | 67.3 / 68.0 | 405.4 | 7.88 |
| | | **16** | 1068 | 1106.5 | **1508** | 1639 | **449.9** | **100.1% (400.4%)** | 21.8% (87.4%) | 99.8 / 100.5 | 409.5 | 8.90 |
| | | **24** | 1126 | 1185.7 | **1799** | 1995 | **417.3** | **100.2% (400.6%)** | 21.2% (84.9%) | 135.2 / 136.4 | 416.8 | 9.60 |
| | | **32** | 1140 | 1244.4 | **2065** | 2287 | **396.6** | **99.9% (399.4%)** | 20.8% (83.1%) | 170.9 / 172.0 | 424.3 | 10.07 |
| | | **40** *(context switch)* | 1110 | 1255.1 | **2264** | 2546 | **391.9** | **100.1% (400.4%)** | 20.9% (83.5%) | 206.2 / 207.2 | 430.9 | 10.22 |
| **EP7** *(Write)* | **1000 VU** | **4** *(domyślny)* | 3566 | 3541.5 | **3821** | 3853 | **275.4** | 40.9% (163.5%) | 10.9% (43.4%) | 52.8 / 53.3 | 406.0 | 5.94 |
| | | **8** *(sufit CPU)* | 2063 | 2065.3 | **2256** | 2327 | **469.9** | **90.3% (361.4%)** | 20.6% (82.4%) | 67.4 / 68.1 | 405.8 | 7.69 |
| | | **16** | 2131 | 2160.3 | **2604** | 2722 | **449.9** | **99.7% (398.9%)** | 21.3% (85.1%) | 100.0 / 100.7 | 410.0 | 8.87 |
| | | **24** | 2224 | 2289.1 | **3029** | 3272 | **424.3** | **99.8% (399.0%)** | 20.9% (83.7%) | 135.5 / 136.4 | 417.0 | 9.40 |
| | | **32** | 2299 | 2418.4 | **3558** | 3891 | **400.8** | **99.9% (399.5%)** | 20.6% (82.4%) | 171.2 / 172.0 | 424.4 | 9.97 |
| | | **40** *(context switch)* | 2248 | 2441.5 | **3866** | 4312 | **395.9** | **99.9% (399.6%)** | 20.5% (82.2%) | 206.4 / 207.4 | 430.9 | 10.09 |

1. **Liniowy model zużycia pamięci RAM przez procesy PHP-FPM:** Zwiększanie liczby workerów od 4 do 40 powoduje idealnie liniowy przyrost pamięci kontenera aplikacji: $52.0\text{ MiB}$ (4 workery) $\rightarrow 66.2\text{ MiB}$ (8) $\rightarrow 98.3\text{ MiB}$ (16) $\rightarrow 133.1\text{ MiB}$ (24) $\rightarrow 168.4\text{ MiB}$ (32) $\rightarrow 202.9\text{ MiB}$ (40 workerów). Oznacza to koszt marginalny ok. **$4.2\text{ MiB}$ prywatnej pamięci (PSS) na każdy dodatkowy proces roboczy PHP-FPM** (dzięki współdzieleniu pamięci kodu bajtowego OPcache w jądrze Linuksa). Nawet przy 40 procesach Laravel zużywa ponad $3\times$ mniej pamięci RAM niż 4 procesy klastra NestJS ($\sim 203\text{ MiB}$ vs $\sim 690–770\text{ MiB}$).
2. **Narzut przełączania kontekstu (Context Switching) na EP7:** Przy 8 workerach na EP7 procesor aplikacji osiąga $99.9\%$ limitu ($507.6\text{ RPS}$, koszt jednostkowy $7.88\text{ ms/req}$). Zwiększanie puli do 16, 24, 32 i 40 procesów utrzymuje CPU na poziomie $100\%$, ale jednostkowy koszt CPU na transakcję rośnie z $7.88\text{ ms}$ do **$10.22\text{ ms}$ ($+29.7\%$)** wskutek narzutu planisty jądra Linuksa na przełączanie kontekstu między 40 procesami konkurującymi o 4 rdzenie vCPU. W efekcie przepustowość spada z $507.6\text{ RPS}$ do $391.9\text{ RPS}$, a $p_{95}$ przy 500 VU pogarsza się z $1166\text{ ms}$ do $2264\text{ ms}$.
3. **Symetryczny dowód dławienia PostgreSQL przy 40 połączeniach na EP3:** Zwiększenie liczby workerów Laravela z 8 do 40 (co zrównuje liczbę równoległych połączeń z domyślną konfiguracją NestJS: 40 połączeń) powoduje spadek przepustowości odczytu z $161.4\text{ RPS}$ do $117.2\text{ RPS}$ oraz eksplozję opóźnienia $p_{95}$ z $6222\text{ ms}$ do **$10\,075\text{ ms}$** przy $99.3\%$ CPU PostgreSQL. Udowadnia to, że wyższe opóźnienie domyślnego NestJS na EP3 wynika wyłącznie z nadmiernej liczby jednoczesnych połączeń do bazy danych (40 vs 4 rdzenie PG), a nie z narzutu Node.js.

---

### 3.2. Pełna analiza wrażliwości puli połączeń NestJS (`DB_POOL_SIZE = 1` vs `10`, $n = 10$) dla EP3 oraz EP7

W artykule w Sekcji 4.2 przedstawiono wyniki `DB_POOL_SIZE = 1` ($n = 10$, `benchmark/results/s2-pool1/summary.csv`) tylko dla endpointu odczytowego **EP3**. W serii głównej ($n = 10$) przebadano również transakcyjny endpoint zapisu **EP7**, co daje pełny obraz kompromisu między dławieniem bazy na odczytach a grupowym zatwierdzaniem transakcji (*group commit*) na zapisach:

| Endpoint | Poziom VU | Konfiguracja | $p_{50} \pm \text{SD}$ (ms) | $p_{95} \pm \text{SD}$ (ms) | $p_{99} \pm \text{SD}$ (ms) | Przepustowość $\pm \text{SD}$ (RPS) | App CPU [% limitu] | PG CPU [% limitu] | CPU / req (ms) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EP3** *(Read)* | **200 VU** | NestJS Pool=10 *(40 conn)* | 1277.0 $\pm$ 192.4 | 1798.5 $\pm$ 175.4 | 2124.5 $\pm$ 227.6 | 144.6 $\pm$ 19.6 | 13.6% | 99.4% | 3.74 |
| | | **NestJS Pool=1 *(4 conn)*** | **982.5 $\pm$ 103.5** | **1138.0 $\pm$ 133.9** | **1203.0 $\pm$ 150.7** | **201.4 $\pm$ 19.2 (+39.3%)** | **14.9%** | **91.7%** | **2.98** |
| | | Laravel *(4 workers)* | 1372.0 $\pm$ 53.6 | 1463.0 $\pm$ 50.1 | 1503.0 $\pm$ 54.0 | 145.7 $\pm$ 5.4 | 35.7% | 63.8% | 9.75 |
| | **500 VU** | NestJS Pool=10 *(40 conn)* | 3578.0 $\pm$ 459.4 | 4113.0 $\pm$ 404.8 | 4355.0 $\pm$ 405.1 | 143.8 $\pm$ 18.6 | 13.6% | 99.5% | 3.75 |
| | | **NestJS Pool=1 *(4 conn)*** | **2634.5 $\pm$ 248.1** | **2953.5 $\pm$ 320.2** | **3093.5 $\pm$ 352.9** | **188.4 $\pm$ 17.6 (+31.0%)** | **14.1%** | **91.6%** | **3.00** |
| | | Laravel *(4 workers)* | 3425.0 $\pm$ 133.5 | 3497.0 $\pm$ 131.5 | 3538.5 $\pm$ 138.6 | 145.4 $\pm$ 5.6 | 35.8% | 64.4% | 9.81 |
| | **1000 VU** | NestJS Pool=10 *(40 conn)* | 6961.5 $\pm$ 612.8 | 7922.5 $\pm$ 652.0 | 8261.0 $\pm$ 679.2 | 142.3 $\pm$ 12.6 | 13.6% | 99.4% | 3.87 |
| | | **NestJS Pool=1 *(4 conn)*** | **5522.0 $\pm$ 566.1** | **6253.5 $\pm$ 673.3** | **6460.5 $\pm$ 721.7** | **179.0 $\pm$ 18.5 (+25.8%)** | **13.5%** | **91.6%** | **3.02** |
| | | Laravel *(4 workers)* | 6838.5 $\pm$ 177.2 | 6903.5 $\pm$ 177.4 | 6948.0 $\pm$ 174.1 | 145.6 $\pm$ 3.8 | 35.7% | 64.6% | 9.80 |
| **EP7** *(Write)* | **200 VU** | NestJS Pool=10 *(40 conn)* | 88.0 $\pm$ 3.3 | 112.0 $\pm$ 5.2 | 126.5 $\pm$ 9.6 | 2194.4 $\pm$ 85.4 | 99.1% | 61.7% | 1.81 |
| | | **NestJS Pool=1 *(4 conn)*** | **192.5 $\pm$ 8.5** | **220.5 $\pm$ 9.6** | **248.5 $\pm$ 12.1** | **1020.5 $\pm$ 41.3 (−53.5%)** | **40.5%** | **23.8%** | **1.59** |
| | | Laravel *(4 workers)* | 434.0 $\pm$ 14.3 | 488.5 $\pm$ 20.6 | 509.5 $\pm$ 23.6 | 453.0 $\pm$ 14.9 | 69.0% | 18.2% | 6.13 |
| | **500 VU** | NestJS Pool=10 *(40 conn)* | 240.0 $\pm$ 8.2 | 275.0 $\pm$ 20.2 | 298.5 $\pm$ 34.4 | 2048.2 $\pm$ 75.8 | 97.3% | 58.6% | 1.90 |
| | | **NestJS Pool=1 *(4 conn)*** | **480.0 $\pm$ 16.5** | **546.5 $\pm$ 20.1** | **588.5 $\pm$ 24.1** | **1028.0 $\pm$ 33.7 (−49.8%)** | **41.6%** | **23.9%** | **1.62** |
| | | Laravel *(4 workers)* | 1142.0 $\pm$ 124.2 | 1300.5 $\pm$ 304.9 | 1347.5 $\pm$ 375.9 | 433.0 $\pm$ 41.3 | 68.3% | 18.1% | 6.16 |
| | **1000 VU** | NestJS Pool=10 *(40 conn)* | 495.0 $\pm$ 21.6 | 559.0 $\pm$ 31.1 | 608.0 $\pm$ 47.4 | 1974.4 $\pm$ 83.2 | 90.0% | 54.1% | 1.83 |
| | | **NestJS Pool=1 *(4 conn)*** | **966.0 $\pm$ 45.4** | **1074.5 $\pm$ 55.4** | **1111.0 $\pm$ 59.8** | **1021.1 $\pm$ 45.7 (−48.3%)** | **42.4%** | **24.0%** | **1.66** |
| | | Laravel *(4 workers)* | 3319.5 $\pm$ 192.6 | 3647.0 $\pm$ 231.1 | 3756.5 $\pm$ 236.2 | 286.3 $\pm$ 16.5 | 43.3% | 11.8% | 6.06 |

**Kluczowy wniosek z EP7 przy `DB_POOL_SIZE = 1` ($n = 10$):**
Gdy ograniczymy NestJS dokładnie do **4 połączeń bazodanowych** (`DB_POOL_SIZE = 1`), przepustowość zapisu transakcyjnego EP7 spada z $\sim 2048–2194\text{ RPS}$ do **$\sim 1020.5–1028.0\text{ RPS}$** (ponieważ tylko 4 transakcje mogą jednocześnie oczekiwać na zrzut dziennika WAL `fsync` w PostgreSQL, co ogranicza efektywność mechanizmu *group commit*). Nawet przy identycznej liczbie 4 połączeń do bazy danych NestJS osiąga jednak **$2.25\times–3.57\times$ wyższą przepustowość** niż Laravel ($1021.1\text{ RPS}$ vs $286.3\text{ RPS}$ przy 1000 VU) i wykazuje całkowity brak załamania przepustowości przy 1000 VU.

---

## 4. Profilowanie warstwy bazodanowej (`pg_stat_statements`) i diagnostyka ścieżki zapisu

### 4.1. Czas wykonania pojedynczych instrukcji SQL po stronie serwera PostgreSQL (EP1–EP9)
Źródło danych: `benchmark/results/smoke/sql-compare-laravel.txt` oraz `sql-compare-nestjs.txt` (20 powtórzeń na każdy endpoint z czyszczeniem `pg_stat_statements_reset()` przed pomiarem).

Poniższa tabela porównuje liczbę instrukcji SQL oraz **rzeczywisty czas wykonania zapytań wewnątrz silnika PostgreSQL (`ms/req`)** między Eloquent ORM (Laravel) a TypeORM (NestJS), wliczając endpointy spoza artykułu (`EP8` jako relacja N:M `dishes/{id}/ingredients` oraz `EP9` jako rezerwacja ze sprawdzaniem kolizji czasowych GiST `POST /api/reservations`):

| Kod w skrypcie | Endpoint HTTP | Instrukcje SQL na żądanie<br>(Laravel / NestJS) | Łączny czas SQL w bazie `ms/req`<br>(Laravel / NestJS) | Rozbicie na poszczególne instrukcje SQL (`mean_ms` w PostgreSQL) |
| :--- | :--- | :---: | :---: | :--- |
| **EP1** | `GET /api/tables` | **1 / 1** | **0.088 ms / 0.097 ms** | `SELECT * FROM tables ORDER BY number ASC`: Lar $0.088\text{ ms}$, Nest $0.097\text{ ms}$ |
| **EP2b** | `GET /api/menu-items?plain=1` | **2 / 2** | **0.119 ms / 0.145 ms** | 1) `COUNT(*)`: Lar $0.044\text{ ms}$, Nest $0.056\text{ ms}$<br>2) `SELECT menu_items ... LIMIT 50`: Lar $0.075\text{ ms}$, Nest $0.089\text{ ms}$ |
| **EP2** | `GET /api/menu-items` *(eager)* | **3 / 3** | **0.194 ms / 0.258 ms** | 1) `COUNT(*)`: Lar $0.045\text{ ms}$, Nest $0.053\text{ ms}$<br>2) `SELECT menu_items`: Lar $0.073\text{ ms}$, Nest $0.115\text{ ms}$<br>3) `SELECT dishes WHERE id IN (...)`: Lar $0.075\text{ ms}$, Nest $0.090\text{ ms}$ |
| **EP3** | `GET /api/orders?page=50` | **4 / 4** | **19.124 ms / 19.723 ms** | 1) `COUNT(*) FROM orders`: Lar **$7.968\text{ ms}$**, Nest **$7.921\text{ ms}$**<br>2) `SELECT orders ... OFFSET 1000 LIMIT 20`: Lar **$11.095\text{ ms}$**, Nest **$11.678\text{ ms}$**<br>3) `SELECT tables WHERE id IN (...)`: Lar $0.025\text{ ms}$, Nest $0.044\text{ ms}$<br>4) `SELECT users WHERE id IN (...)`: Lar $0.036\text{ ms}$, Nest $0.080\text{ ms}$ |
| **EP4** | `GET /api/orders/{id}` *(nested)* | **5 / 5** | **0.517 ms / 0.659 ms** | 1) `SELECT orders WHERE id = $1`: Lar $0.036\text{ ms}$, Nest $0.059\text{ ms}$<br>2) `SELECT order_items WHERE order_id IN`: Lar $0.391\text{ ms}$, Nest $0.451\text{ ms}$<br>3) `SELECT dishes WHERE id IN`: Lar $0.046\text{ ms}$, Nest $0.064\text{ ms}$<br>4) `SELECT users WHERE id IN`: Lar $0.024\text{ ms}$, Nest $0.049\text{ ms}$<br>5) `SELECT tables WHERE id IN`: Lar $0.020\text{ ms}$, Nest $0.037\text{ ms}$ |
| **EP5** *(w S1)* | `PATCH /api/orders/{id}/status` | **2 / 5** | **0.175 ms / 0.190 ms** | Lar: `SELECT orders` ($0.041\text{ ms}$) + `UPDATE orders` ($0.135\text{ ms}$)<br>Nest: $2\times$ `SELECT orders` ($0.088\text{ ms}$) + `START TX` + `UPDATE ... RETURNING` ($0.099\text{ ms}$) + `COMMIT` |
| **EP6** | `GET /api/dashboard/summary` | **1 / 1** | **138.28 ms / 145.67 ms** | 3-table `JOIN` + `GROUP BY`: Lar **$138.284\text{ ms}$**, Nest **$145.673\text{ ms}$** |
| **EP7** | `POST /api/orders` *(tx write)* | **7 / 7** | **0.354 ms / 0.369 ms** | `BEGIN` + `SELECT dishes` ($0.05\text{ ms}$) + `SELECT menu_items` ($0.04\text{ ms}$) + `INSERT orders` ($0.11\text{ ms}$) + `INSERT order_items` ($0.07\text{ ms}$) + `UPDATE orders total_price` ($0.08\text{ ms}$) + `COMMIT` |
| **EP8** *(pivot N:M)* | `GET /api/dishes/{id}/ingredients` | **2 / 2** | **0.258 ms / 0.251 ms** | 1) `SELECT dishes WHERE id = $1`: Lar $0.029\text{ ms}$, Nest $0.045\text{ ms}$<br>2) `SELECT ingredients INNER JOIN dish_ingredients`: Lar $0.229\text{ ms}$, Nest $0.207\text{ ms}$ |
| **EP9** *(GiST)* | `POST /api/reservations` *(GiST)* | **6 / 6** | **0.464 ms / 0.562 ms** | `BEGIN` + `SELECT tables FOR UPDATE` ($0.05\text{ ms}$) + `SELECT EXISTS (... tsrange && tsrange)` ($0.24\text{ ms}$) + `INSERT reservations` ($0.16\text{ ms}$) + `COMMIT` |

1. **Różnica czasu SQL dla prostych odczytów (EP1, EP2b, EP2, EP4, EP8) wynosi poniżej $0.15\text{ ms}$:** W EP1 sam silnik PostgreSQL wykonuje zapytanie w **$0.088\text{ ms}$** (Laravel) oraz **$0.097\text{ ms}$** (NestJS). Cała pozostała część czasu odpowiedzi ($6.5\text{ ms}$ w Laravelu vs $1.2\text{ ms}$ w NestJS) to czysty narzut warstwy aplikacyjnej i komunikacji z procesem roboczym!
2. **Dekonstrukcja czasu zapytania EP3 (`page=50`, `OFFSET 1000`):** Czas wykonania 4 zapytań w bazie wynosi łącznie **$19.12\text{ ms}$** w Laravelu i **$19.72\text{ ms}$** w NestJS, z czego $99.6\%$ czasu pochłaniają dwie operacje: pełne zliczanie tabeli `SELECT count(*) FROM orders` ($\sim 7.95\text{ ms}$) oraz skanowanie z przesunięciem `OFFSET 1000 LIMIT 20` ($\sim 11.1–11.7\text{ ms}$). Eager loading relacji `tables` i `users` za pomocą klauzuli `WHERE id IN (...)` zajmuje łącznie zaledwie **$0.06–0.12\text{ ms}$**.

---

### 4.2. Diagnostyka asymetrii zapisu w EP8 (`PATCH /api/orders/{id}/status`) – `X-Query-Count` vs `pg_stat_statements`
Źródło danych: `benchmark/results/smoke/ep8-diagnostic-20261006.txt`.

W toku badania przeprowadzono szczegółowy eksperyment diagnostyczny dla endpointu aktualizacji statusu zamówienia (`PATCH /api/orders/1/status`, oznaczanego jako EP8 w pilotażu S1 oraz EP5 w serii głównej S1), porównując przypadek, w którym przesłany status jest identyczny z aktualnym statusem w bazie (`paid` $\rightarrow$ `paid`), oraz przypadek faktycznej zmiany wartości (`paid` $\rightarrow$ `open`):

| Framework | Przypadek testowy | Kod HTTP | Nagłówek `X-Query-Count` | Rzeczywista liczba instrukcji w `pg_stat_statements` | Zarejestrowane instrukcje SQL i czas wykonania |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Laravel** | Brak zmiany (`paid` $\rightarrow$ `paid`) | 200 | `0` | **1** | 1) `SELECT * FROM "orders" WHERE "id" = $1 LIMIT $2` ($0.145\text{ ms}$) – Eloquent *dirty checking* wykrywa brak zmiany atrybutu i pomija `UPDATE`! |
| **NestJS** | Brak zmiany (`paid` $\rightarrow$ `paid`) | 200 | `1` | **2** | 1) `SELECT ... FROM "orders" WHERE "id" = $1` ($0.015\text{ ms}$, `BindOrderGuard`)<br>2) `SELECT ... FROM "orders" WHERE "id" = $1 LIMIT $2` ($0.068\text{ ms}$, TypeORM) |
| **Laravel** | Zmiana wartości (`paid` $\rightarrow$ `open`) | 200 | `1` | **2** | 1) `SELECT * FROM "orders" WHERE "id" = $1 LIMIT $2` ($0.031\text{ ms}$)<br>2) `UPDATE "orders" SET "status" = $1, "updated_at" = $2 WHERE "id" = $3` ($3.087\text{ ms}$) |
| **NestJS** | Zmiana wartości (`paid` $\rightarrow$ `open`) | 200 | `4` | **5** | 1) `SELECT` w `BindOrderGuard` ($0.009\text{ ms}$)<br>2) `SELECT` przed zapisem w `TypeORM.save()` ($0.033\text{ ms}$)<br>3) `START TRANSACTION` ($0.001\text{ ms}$)<br>4) `UPDATE "orders" SET "status" = $1, "updated_at" = CURRENT_TIMESTAMP WHERE "id" = $2 RETURNING "updated_at"` ($1.585\text{ ms}$)<br>5) `COMMIT` ($0.001\text{ ms}$) |

1. Poleganie wyłącznie na aplikacyjnym liczniku zapytań (`DB::getQueryLog()` w middleware Laravela oraz `QueryCountInterceptor` w NestJS) dawało niepełny obraz, ponieważ w Laravelu *Route Model Binding* (bądź odpowiedni middleware) oraz w NestJS `BindOrderGuard` wykonywały zapytanie `SELECT` przed wejściem w zakres pomiaru interceptora. Dopiero weryfikacja przez `pg_stat_statements` ujawniła pełną ścieżkę SQL.
2. W teście obciążeniowym JMeter losuje status spośród 4 dozwolonych wartości (`open`, `paid`, `cancelled`, `completed`), co oznacza, że w $25\%$ żądań nowy status pokrywa się z dotychczasowym (gdzie mechanizm *dirty checking* w Eloquent ORM pozwala Laravelowi pominąć instrukcję `UPDATE`). Mimo że NestJS wykonuje przy zmianie statusu 5 instrukcji SQL (wobec 2 w Laravelu), to i tak osiąga ponad $2\times$ krótszy czas odpowiedzi ($4.0\text{ ms}$ vs $8.0\text{ ms}$), co dodatkowo wzmacnia wniosek o odrzuceniu hipotezy H1.

---

### 4.3. Weryfikacja trwałych połączeń PDO (`PDO::ATTR_PERSISTENT`) w Laravelu
W celu wykluczenia hipotezy alternatywnej, że stały narzut $\sim 6\text{ ms}$ na żądanie w Laravelu wynika z każdorazowego zestawiania połączenia TCP i uwierzytelniania w PostgreSQL, przeprowadzono weryfikację konfiguracji sterownika `pgsql` (`config/database.php`). Potwierdzono, że flaga `PDO::ATTR_PERSISTENT => true` jest aktywna we wszystkich testach, dzięki czemu każdy z 4 procesów roboczych PHP-FPM utrzymuje stałe, otwarte gniazdo do PostgreSQL pomiędzy kolejnymi żądaniami HTTP. Eliminuje to koszt TCP/auth handshake i dowodzi, że narzut $\sim 5–6\text{ ms}$ CPU na żądanie pochodzi wyłącznie z inicjalizacji cyklu życia żądania w kontenerze IoC Laravela, potoku middleware, hydratacji modeli Eloquent oraz serializacji JSON.

---

## 5. Wyniki badań pilotażowych ($n = 1$) i serii eksploracyjnych

Przed uruchomieniem 10-krotnej serii głównej przeprowadzono formalną kampanię pilotażową ($n = 1$, rozgrzewka 60 s, pomiar 60 s), której celem była weryfikacja stabilności obrazów Docker, bramek integralności danych oraz wyznaczenie przedziałów obciążenia spełniających *Low-Load Validity Rule*. Co istotne, w pilotażach przebadano również dodatkowe kombinacje endpointów, które nie weszły do ostatecznych tabel w artykule.

### 5.1. Pilotaż Scenariusza S1 (EP1, EP2, EP8 przy 1–10 VU) i walidacja reguły niskiego obciążenia
Źródło danych: `benchmark/results/smoke/s1-h1-pilot-20261005/summary.csv` oraz `dokumenty/wyniki/wynik_p_h1.md`.
W pilotażu S1 obok `EP1` i `EP8` (odpowiadającego `EP5` w serii głównej) przebadano również `EP2` (`GET /api/menu-items` z 1 relacją eager loading).

| Endpoint | Poziom VU | Przepustowość (RPS)<br>Laravel / NestJS | $p_{50}$ (ms)<br>Lar / Nest | Średnia (ms)<br>Lar / Nest | $p_{95}$ (ms)<br>Lar / Nest | $p_{99}$ (ms)<br>Lar / Nest | Współczynnik skalowania $X(N)/(N \cdot X(1))$<br>Laravel / NestJS | App CPU [% limitu]<br>Laravel / NestJS | CPU / req (ms)<br>Lar / Nest |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EP1** *(no rel)* | 1 VU | 163.2 / 832.0 | 6 / 1 | 6.02 / 1.16 | **7 / 2** | 8 / 2 | 1.000 / 1.000 | 21.7% / 17.7% | 5.32 / 0.85 |
| | 2 VU | 338.8 / 1639.8 | 6 / 1 | 5.83 / 1.18 | **7 / 2** | 8 / 2 | **1.038 / 0.985** *(PASS)* | 42.8% / 34.4% | 5.05 / 0.84 |
| | 4 VU | 648.6 / 3009.3 | 6 / 1 | 6.09 / 1.29 | **7 / 2** | 8 / 3 | 0.994 / 0.904 | **86.7%** *(FAIL)* / 68.1% | 5.35 / 0.91 |
| | 10 VU | 612.8 / 4016.2 | 16 / 2 | 16.22 / 2.44 | **22 / 4** | 27 / 8 | **0.376 / 0.483** *(FAIL)* | **88.8% / 99.7%** *(FAIL)* | 5.79 / 0.99 |
| **EP2** *(1 rel)* | 1 VU | 107.7 / 466.0 | 9 / 2 | 9.10 / 2.09 | **10 / 3** | 11 / 3 | 1.000 / 1.000 | 21.4% / 18.2% | 7.96 / 1.56 |
| | 2 VU | 247.6 / 918.2 | 8 / 2 | 7.99 / 2.12 | **10 / 3** | 12 / 3 | **1.149 / 0.985** *(PASS)* | 42.7% / 34.5% | 6.90 / 1.50 |
| | 4 VU | 519.1 / 1622.0 | 7 / 2 | 7.64 / 2.42 | **9 / 3** | 11 / 4 | 1.205 / 0.870 | **85.6%** *(FAIL)* / 65.8% | 6.60 / 1.62 |
| | 10 VU | 522.3 / 2516.1 | 19 / 4 | 19.05 / 3.92 | **23 / 6** | 27 / 11 | **0.485 / 0.540** *(FAIL)* | **87.4% / 98.4%** *(FAIL)* | 6.69 / 1.56 |
| **EP8** *(UPDATE)* | 1 VU | 164.9 / 397.1 | 6 / 3 | 5.95 / 2.47 | **8 / 4** | 9 / 5 | 1.000 / 1.000 | 18.4% / 12.2% | 4.46 / 1.22 |
| | 2 VU | 331.2 / 768.0 | 6 / 3 | 5.95 / 2.55 | **8 / 4** | 9 / 5 | **1.004 / 0.967** *(PASS)* | 36.7% / 22.3% | 4.43 / 1.16 |
| | 4 VU | 664.8 / 1331.9 | 6 / 3 | 5.94 / 2.95 | **8 / 5** | 9 / 5 | 1.008 / 0.838 | 71.8% / 39.9% | 4.32 / 1.20 |
| | 10 VU | 679.0 / 2577.5 | 14 / 4 | 14.63 / 3.82 | **18 / 6** | 20 / 7 | **0.412 / 0.649** *(FAIL)* | 74.0% / 78.8% | 4.36 / 1.22 |

---

### 5.2. Pilotaż Scenariusza S2 (EP3, EP7 przy 200–1000 VU) oraz kontrola bramek spójności danych
Źródło danych: `benchmark/results/smoke/s2-h2-pilot-20261006/summary.csv`, `s2-pool1-pilot-20261006/summary.csv` oraz `dokumenty/wyniki/wynik_p_h2.md`.

| Endpoint | Poziom VU | Przepustowość (RPS)<br>Laravel / Nest (P=1) / Nest (P=10) | $p_{95}$ (ms)<br>Laravel / Nest (P=1) / Nest (P=10) | PG CPU [% limitu]<br>Laravel / Nest (P=1) / Nest (P=10) | App CPU [% limitu]<br>Laravel / Nest (P=1) / Nest (P=10) | Wstawione wiersze $\Delta\text{orders}$ (= HTTP 201)<br>Laravel / Nest (P=1) / Nest (P=10) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **EP3** *(Read)* | 200 VU | 112.5 / **199.1** / 148.4 | 2299 / **1170** / 1903 | 61.0% / **88.3%** / 100.2% | 34.0% / 15.0% / 14.6% | 0 / 0 / 0 *(tylko odczyt)* |
| | 500 VU | 121.1 / **198.7** / 137.6 | 4710 / **2806** / 4500 | 61.5% / **88.3%** / 100.0% | 33.6% / 15.0% / 14.8% | 0 / 0 / 0 *(tylko odczyt)* |
| | 1000 VU | 126.6 / **202.1** / 143.0 | 8318 / **5432** / 8374 | 61.3% / **88.3%** / 100.0% | 33.8% / 15.3% / 14.6% | 0 / 0 / 0 *(tylko odczyt)* |
| **EP7** *(Write)* | 200 VU | 405.0 / **1045.3** / 2231.4 | 601 / **226** / 115 | 16.3% / **23.7%** / 62.7% | 64.3% / 41.2% / 98.1% | +47 622 / +122 255 / +255 897 *(100% zgodności)* |
| | 500 VU | 387.5 / **1042.0** / 2022.1 | 1439 / **568** / 312 | 16.1% / **23.6%** / 62.0% | 63.2% / 42.2% / 98.9% | +47 009 / +121 754 / +239 958 *(100% zgodności)* |
| | 1000 VU | 388.7 / **1021.8** / 2135.6 | 2861 / **1089** / 546 | 16.0% / **23.9%** / 60.7% | 62.7% / 43.1% / 99.8% | +47 826 / +122 937 / +246 745 *(100% zgodności)* |

---

### 5.3. Pilotaż Scenariusza S3 (z uwzględnieniem relacji N:M przez tabelę pivot – `EP5: GET /api/dishes/{id}/ingredients`)
Źródło danych: `benchmark/results/smoke/s3-h3-pilot-20261007/summary.csv` oraz `dokumenty/wyniki/wynik_p_h3.md`.

W pilotażu S3 przebadano dodatkowy endpoint relacyjny **`EP5: GET /api/dishes/{id}/ingredients`** (relacja wiele-do-wielu N:M przez tabelę łączącą `dish_ingredients`), który został później pominięty w serii głównej na rzecz pary `EP2b` vs `EP2`. Wyniki pilotażu dla tego endpointu pokazują interesującą właściwość:

| Endpoint w pilotażu S3 | Poziom VU | Przepustowość (RPS)<br>Laravel / NestJS | $p_{50}$ (ms)<br>Lar / Nest | Średnia (ms)<br>Lar / Nest | $p_{95}$ (ms)<br>Lar / Nest | Luka $S_k$ (ms) | Kontrast $D_k = S_k - S_{\text{EP1}}$ (ms) | App CPU [% limitu]<br>Laravel / NestJS | CPU / req (ms)<br>Lar / Nest |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **EP1** *(baseline `tables`)* | 1 VU | 170.9 / 810.0 | 6 / 1 | 5.75 / 1.18 | **7 / 2** | 5.0 ms | Baseline ($0.0\text{ ms}$) | 22.0% / 17.9% | 5.15 / 0.89 |
| | 2 VU | 331.3 / 1603.9 | 6 / 1 | 5.95 / 1.20 | **8 / 2** | 6.0 ms | Baseline ($0.0\text{ ms}$) | 43.7% / 34.9% | 5.28 / 0.87 |
| **EP4** *(3-lvl nested `orders/{id}`)* | 1 VU | 111.4 / 366.5 | 9 / 3 | 8.83 / 2.67 | **11 / 3** | 8.0 ms | **+3.00 ms** | 20.2% / 16.2% | 7.25 / 1.77 |
| | 2 VU | 219.6 / 701.0 | 9 / 3 | 8.98 / 2.79 | **11 / 4** | 7.0 ms | **+1.00 ms** *(Mean: +1.44 ms)* | 40.4% / 30.9% | 7.37 / 1.76 |
| **EP5** *(N:M pivot `dishes/{id}/ingredients`)* | 1 VU | 177.4 / 828.0 | 5 / 1 | 5.56 / 1.17 | **7 / 2** | 5.0 ms | **0.00 ms** | 21.5% / 15.9% | 4.86 / 0.77 |
| | 2 VU | 345.9 / 1580.9 | 6 / 1 | 5.69 / 1.23 | **7 / 2** | 5.0 ms | **−1.00 ms** | 42.8% / 31.0% | 4.95 / 0.78 |
| | 4 VU | 604.1 / 2783.0 | 6 / 1 | 6.52 / 1.40 | **9 / 2** | 7.0 ms | 0.00 ms | 85.8% / 61.9% | 5.68 / 0.89 |
| | 10 VU | 542.1 / 4072.8 | 17 / 2 | 18.26 / 2.40 | **27 / 4** | 23.0 ms | +8.00 ms | 88.0% / 99.9% | 6.49 / 0.98 |
| **EP6** *(3 JOIN + GROUP BY)* | 1 VU | 8.1 / 8.3 | 120 / 117 | 122.15 / 119.44 | **139 / 133** | 6.0 ms | +1.00 ms | 1.2% / 0.7% | 5.99 / 3.19 |
| | 2 VU | 15.3 / 15.6 | 127 / 125 | 129.62 / 127.61 | **154 / 155** | −1.0 ms | **−7.00 ms** | 2.2% / 0.9% | 5.73 / 2.40 |
| | 4 VU | 26.7 / 27.9 | 146 / 140 | 148.59 / 142.56 | **174 / 168** | 6.0 ms | −1.00 ms | 4.0% / 1.5% | 6.05 / 2.12 |
| | 10 VU | 27.5 / 20.1 | 363 / 495 | 361.82 / 492.74 | **430 / 573** | −143.0 ms | **−158.00 ms** | 4.0% / 1.3% | 5.82 / 2.56 |

Relacja wiele-do-wielu dla pojedynczego dania zwraca niewielką kolekcję składników (średnio kilka rekordów z tabeli `ingredients` złączonej przez `dish_ingredients`). Zarówno w Laravelu ($177.4\text{ RPS}$ przy 1 VU, $p_{95} = 7\text{ ms}$, koszt CPU $4.86\text{ ms/req}$), jak i w NestJS ($828.0\text{ RPS}$ przy 1 VU, $p_{95} = 2\text{ ms}$, koszt CPU $0.77\text{ ms/req}$) endpoint ten jest nawet minimalnie szybszy niż odczyt wszystkich 50 stolików z tabeli `tables` (`EP1`), a kontrast $D_{\text{EP5}}$ wynosi $0.00\text{ ms}$ (1 VU) oraz $-1.00\text{ ms}$ (2 VU). Dowodzi to, że samo istnienie złączenia `INNER JOIN` przez tabelę pośredniczącą (pivot) nie generuje mierzalnego narzutu w żadnym z badanych ORM-ów, o ile liczba nawadnianych obiektów docelowych jest mała.

---

### 5.4. Wczesny pilotaż eksploracyjny (10–1000 VU, `EP9: POST /api/reservations` z indeksem GiST oraz incydent `keepalive_requests`)
Źródło danych: `dokumenty/notatki/03_notatki_z_odrzucenia_hipotez.md` (część III).

W pierwszym pilotażu eksploracyjnym (przeprowadzonym dla pełnej siatki 10, 50, 100, 200, 500 i 1000 VU przed zamrożeniem protokołu serii głównej) zidentyfikowano dwa niezwykle istotne zjawiska inżynieryjne:
1. **Złożony zapis z blokadą pesymistyczną i indeksem GiST (`EP9: POST /api/reservations`):**
   - Endpoint ten weryfikuje brak nakładania się przedziałów czasowych rezerwacji stolika za pomocą operatora `&&` na typie `tsrange` wspieranym przez indeks przestrzenny **GiST** oraz blokadę wiersza `SELECT ... FOR UPDATE`.
   - Przy 10 VU oba frameworki uzyskały zbliżony czas odpowiedzi $p_{95}$ ($18\text{ ms}$ w Laravelu vs $15\text{ ms}$ w NestJS), natomiast wraz ze wzrostem współbieżności do 1000 VU NestJS utrzymał ponad $2\times$ niższe opóźnienie ogona ($p_{95} = 2472\text{ ms}$ przy $413.4\text{ RPS}$) niż Laravel ($p_{95} = 5379\text{ ms}$ przy $188.6\text{ RPS}$).
2. **Wyczerpanie portów efemerycznych TCP przy domyślnym `keepalive_requests` w Nginx:**
   - W pierwszym przebiegu pilotażowym dla NestJS przy 200 VU na szybkich endpointach (`EP1`, `EP7`, gdzie przepustowość przekraczała $2000–3500\text{ RPS}$) zaobserwowano nagły skok błędów sieciowych ($9.38\%$ błędów na EP7 przy 200 VU).
   - Analiza wykazała, że domyślny limit Nginx `keepalive_requests = 1000` wymuszał zamykanie i ponowne otwieranie gniazd TCP co 1000 żądań, co przy przepustowości $\sim 3500\text{ RPS}$ generowało tysiące gniazd w stanie `TIME_WAIT` na sekundę i wyczerpywało pulę portów efemerycznych w stosie sieciowym kontenera.
   - Podniesienie parametru `keepalive_requests` w konfiguracji Nginx całkowicie wyeliminowało błędy (**0.00% error rate** we wszystkich późniejszych pilotażach i w całej serii głównej $n = 10$). 

---

