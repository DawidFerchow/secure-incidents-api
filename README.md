# Secure Incidents API
Prosta aplikacja CRUD wraz z lokalnym środowiskiem do zbierania logów i pipeline'em CI/CD z Quality Gate.

## Aplikacja
### Specyfikacja
Zasobem aplikacji są wpisy wygenerowane automatyczne o incydentach bezpieczeństwa, zawierający pola:
- `title`,
- `description`,
- `severity`: `low`, `medium`, `high`, `critical`,
- `status`: `open`, `investigating`, `resolved`.

Przy starcie aplikacja ładuje do pamięci 2500 rekordów (liczbę można zmienić poprzez zmienne środowiskowe).

| Metoda   | Endpoint                 | Działanie |
| -------- | ------------------------ | --------- |
| `GET`    | `/api/v1/incidents`      | Lista     |
| `GET`    | `/api/v1/incidents/{id}` | Szczegóły |
| `POST`   | `/api/v1/incidents`      | Dodanie   |
| `PUT`    | `/api/v1/incidents/{id}` | Edycja    |
| `DELETE` | `/api/v1/incidents/{id}` | Usunięcie |

Lista korzysta z Cursor pagination. `limit` wynosi domyślnie 50 i maksymalnie 100, a `next_cursor` wskazuje następną stronę:
```shell
curl "http://localhost:8080/api/v1/incidents?limit=50&after_id=100"
```

Dostępne jest również filtrowanie po `severity` i `status`:
```shell
curl "http://localhost:8080/api/v1/incidents?severity=critical&status=open"
```

### Środowisko
Wymagania:
- Docker Engine
- Docker Compose

Uruchomienie:
```shell
docker compose up --build -d
```

Po uruchomieniu mamy do dyspozycji:
- API i Swagger UI: [http://localhost:8080/docs](http://localhost:8080/docs),
- Grafanę z gotowym dashboardem: [http://localhost:3000](http://localhost:3000),
- readiness endpoint: [http://localhost:8080/health/ready](http://localhost:8080/health/ready).

Grafana działa bez konieczności logowania się do aplikacji. Logi można wygenerować poprzez cURL, Swagger UI lub poczekać (pojawią się logi z readiness).

Zatrzymanie:
```shell
docker compose down
```

Zatrzymanie z usunięciem woluminów:
```shell
docker compose down -v
```

### Logi
Aplikacja zapisuje strukturalne logi JSON na **stdout**. Logi requestów zawierają między innymi:
- czas w UTC,
- poziom i nazwę zdarzenia,
- `request_id`,
- metodę i ścieżkę,
- status HTTP,
- czas obsługi.

Treści samych requestów nie są logowane. Przychodzący `X-Request-ID` jest walidowany, a w przypadku jego braku aplikacja generuje UUID.

**Alloy** pobiera logi oznaczonego kontenera przez Docker API i wysyła je do Loki. Grafana ma automatycznie skonfigurowane źródło danych oraz dashboard z liczbą requestów, błędów, statusami HTTP i strumieniem logów.
### Testy lokalne
Do uruchomienia testów poza kontenerem potrzebne są Python 3.12 i [uv](https://docs.astral.sh/uv/).

```shell
uv sync --frozen --all-groups
make check
make test
make audit
```

Testy obejmują paginację, filtrowanie, pełny cykl CRUD, walidację danych, healthcheck, limity oraz zachowanie `X-Request-ID`.

### Obraz aplikacji
Obraz aplikacji jest budowany wieloetapowo, działa jako użytkownik bez uprawnień roota i instaluje zależności z hashami wygenerowanymi z `uv.lock`. Compose dodatkowo ustawia read-only filesystem, `no-new-privileges` i usuwa Linux capabilities.

Mount `/var/run/docker.sock` w Alloy jest świadomym kompromisem dla prostego środowiska lokalnego. W produkcji zastosowałbym ograniczony socket proxy albo mechanizm zbierania logów właściwy dla platformy, np. Kubernetes.

## CI/CD i Quality Gate
### Pipeline 
Pipeline znajduje się w `.github/workflows/ci.yml` i składa się z trzech etapów:

1. **Code and tests** - Ruff, pytest i coverage.
2. **Source security** - Gitleaks, Bandit i `pip-audit`.
3. **Container and delivery** - walidacja Compose, budowa obrazu, Trivy, smoke test, SBOM i publikacja do GHCR.

Publikacja obrazu kontenera jest blokowana, jeśli:
- formatowanie lub lint zwracają błąd,
- nie przechodzi dowolny test,
- coverage spada poniżej 80%,
- zostanie wykryty sekret, problem SAST albo podatna zależność,
- Trivy znajdzie naprawialną podatność `HIGH` lub `CRITICAL`,
- kontener nie przejdzie healthchecka i testowego cyklu CRUD.

Po pozytywnym przejściu Quality Gate dla `main` ten sam sprawdzony obraz jest publikowany do GHCR z tagiem SHA commita oraz `latest`. Pipeline zapisuje również CycloneDX SBOM jako artefakt workflow.

### Manualna konfiguracja repozytorium
Sam plik workflow nie blokuje bezpośrednich zmian w domyślnej gałęzi. W repozytorium należy utworzyć aktywny GitHub Ruleset dla domyślnej gałęzi (`Settings → Rules → Rulesets`) i włączyć `Require a pull request before merging`, `Require status checks to pass`, `Require branches to be up to date before merging` oraz `Block force pushes`. Lista osób i aplikacji mogących ominąć regułę powinna pozostać pusta. W jednoosobowym projekcie liczba wymaganych akceptacji PR może wynosić `0`.

Jako wymagane status checks należy wskazać:
- `Quality Gate — code and tests`,
- `Quality Gate — source security`,
- `Quality Gate — container and delivery`.

Po włączeniu reguły lokalne commity oraz push do gałęzi roboczych pozostają dozwolone, ale bezpośredni push do domyślnej gałęzi jest blokowany. Zmiany muszą zostać przesłane przez Pull Request. Trigger `pull_request` w `.github/workflows/ci.yml` uruchamia Quality Gate po utworzeniu oraz każdej aktualizacji PR, a merge pozostaje zablokowany do czasu pomyślnego zakończenia wszystkich wymaganych kontroli.

## Wybrane narzędzia z uzasadnieniem

| Narzędzie                 | Rola                                             | Dlaczego ten wybór                                                                                                                                                                                                            |
| ------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FastAPI                   | Implementacja REST API                           | Zapewnia walidację przez Pydantic i automatyczną dokumentację OpenAPI. W porównaniu z Flaskiem wymaga mniej ręcznej konfiguracji, a Django byłoby zbyt rozbudowane dla prostego API in-memory.                                |
| uv                        | Zarządzanie środowiskiem i zależnościami Pythona | Łączy tworzenie virtualenv, rozwiązywanie zależności, lockfile i uruchamianie poleceń. Upraszcza konfigurację względem osobnego używania `venv`, `pip` i narzędzia do generowania lockfile.                                   |
| pytest                    | Testy aplikacji                                  | Dobrze integruje się z `TestClient` FastAPI, oferuje proste fixtures i czytelne asercje. Pozwala testować API bez uruchamiania osobnego serwera lub kontenera.                                                                |
| Ruff                      | Formatowanie i statyczna kontrola jakości        | Jednym szybkim narzędziem zastępuje kilka osobnych elementów, takich jak Black, isort i część reguł Flake8. Ogranicza liczbę zależności oraz konfiguracji w pipeline.                                                         |
| Bandit                    | SAST kodu Python                                 | Jest wyspecjalizowany w wykrywaniu niebezpiecznych konstrukcji w Pythonie, działa bez zewnętrznego serwera i łatwo zwraca kod błędu blokujący pipeline. SonarQube byłby nieproporcjonalnie ciężki dla projektu tej wielkości. |
| pip-audit                 | SCA zależności Pythona                           | Sprawdza używane pakiety względem baz znanych podatności. Został wybrany zamiast ogólnego skanera zależności, ponieważ jest lekki i dopasowany bezpośrednio do ekosystemu Pythona.                                            |
| Gitleaks                  | Wykrywanie sekretów                              | Analizuje historię Git, a nie tylko aktualny stan plików. Uzupełnia SAST, ponieważ token lub hasło nie musi być podatnością w kodzie, ale nadal stanowi zagrożenie dla procesu dostarczania.                                  |
| Trivy                     | Skanowanie obrazu i SBOM                         | Jednym narzędziem analizuje finalny obraz pod kątem podatności systemowych i aplikacyjnych oraz generuje SBOM w formacie CycloneDX. Eliminuje potrzebę utrzymywania osobnych narzędzi do tych dwóch zadań.                    |
| Loki                      | Przechowywanie i wyszukiwanie logów              | Indeksuje głównie etykiety zamiast pełnej treści logów, dzięki czemu jest prostszy i lżejszy operacyjnie niż stos Elasticsearch dla niewielkiego środowiska demonstracyjnego. Integruje się bezpośrednio z Grafaną.           |
| Grafana Alloy             | Zbieranie i przetwarzanie logów                  | Potrafi wykrywać kontenery przez Docker API, odczytywać ich logi, parsować JSON i przekazywać dane bezpośrednio do Loki. Jako element ekosystemu Grafany ogranicza liczbę różnych technologii w stosie obserwowalności.       |
| Grafana                   | Wizualizacja logów                               | Ma natywne wsparcie dla Loki oraz provisioning źródeł danych i dashboardów z plików. Dzięki temu użytkownik otrzymuje gotowy widok bez ręcznej konfiguracji po uruchomieniu Compose.                                          |
| GitHub Actions            | CI/CD i Quality Gate                             | Integruje się bezpośrednio z repozytorium, Pull Requestami i branch protection. Nie wymaga utrzymywania osobnego serwera CI, jak w przypadku samodzielnej instalacji Jenkinsa.                                                |
| GitHub Container Registry | Przechowywanie obrazów                           | Wykorzystuje uprawnienia i token dostępny już w GitHub Actions. Pozwala publikować obraz bez konfigurowania osobnego konta, registry i dodatkowych sekretów.                                                                  |
## Ograniczenia
- Dane są przechowywane in-memory i znikają po restarcie aplikacji.
- Aplikacja działa w jednym procesie, ponieważ osobne workery posiadałyby niezależne magazyny danych.
- Brak uwierzytelniania wynika z ograniczonego zakresu zadania. W obecnej postaci API jest przeznaczone wyłącznie do uruchomienia lokalnego.
## Co dodałbym, mając więcej czasu
Dalszy rozwój rozpocząłbym od uproszczonego modelu zagrożeń, aby kolejne zabezpieczenia wynikały z rzeczywistego ryzyka. 

- W pierwszej kolejności dodałbym uwierzytelnianie OIDC, role użytkowników oraz testy negatywne autoryzacji. 
- Następnie rozszerzyłbym pipeline o DAST z wykorzystaniem OWASP ZAP i schematu OpenAPI. 
- Kolejnym krokiem byłoby podpisywanie obrazów, generowanie informacji o ich pochodzeniu oraz wdrażanie po niezmiennym digescie zamiast tagu `latest`. 
- Pipeline uzupełniłbym również o kontrolowane wdrożenie na środowisko staging, testy po wdrożeniu i mechanizm rollbacku. 
- W dalszej kolejności dodałbym TLS, rate limiting, cykliczne skanowanie już opublikowanych obrazów oraz ograniczony Docker socket proxy dla kolektora logów. 

Elementy te nie zostały wdrożone ze względu na czas i zakres zadania, ale stanowiłyby naturalny kolejny etap rozwoju rozwiązania.
