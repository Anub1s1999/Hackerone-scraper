# HackerOne Scrapper (Leaderboard → Profiles → CSV/Neo4j)

- **English README**: jump to [EN](#english)
- **Русская версия**: перейти к [RU](#русский)

---

## English

### Table of contents (EN)

- [What this project does](#what-this-project-does)
- [How it works (high level)](#how-it-works-high-level)
- [Outputs](#outputs)
- [Requirements](#requirements)
- [Install](#install)
- [Usage](#usage)
- [Demo (screenshots + video)](#demo-screenshots--video)
- [Technical details (deep dive)](#technical-details-deep-dive)
- [Troubleshooting](#troubleshooting)
- [Ethics, legality, and site terms](#ethics-legality-and-site-terms)
- [Project structure](#project-structure)

### Technical table of contents (EN)

- [Data flow and module responsibilities](#data-flow-and-module-responsibilities)
  - [`main.py` orchestration](#mainpy-orchestration)
  - [`get_users.py` leaderboard extraction](#get_userspy-leaderboard-extraction)
  - [`profile_scraper.py` profile scraping](#profile_scraperpy-profile-scraping)
  - [`export_csv.py` CSV export + Neo4j import helper](#export_csvpy-csv-export--neo4j-import-helper)
- [Extraction strategy (why JavaScript in the page)](#extraction-strategy-why-javascript-in-the-page)
- [Anti-bot/CAPTCHA handling](#anti-botcaptcha-handling)
- [Rate limiting and politeness delays](#rate-limiting-and-politeness-delays)
- [Data model](#data-model)
  - [Hacker fields](#hacker-fields)
  - [Contribution fields](#contribution-fields)
- [Neo4j import notes](#neo4j-import-notes)
- [Known limitations](#known-limitations)

### What this project does

This repo scrapes a **subset of HackerOne leaderboard users** and then scrapes each user’s **public profile** to produce:

- **A list of usernames** (from the leaderboard page)
- **Structured profile data** for each username
- **Two CSVs** designed to be easy to import into **Neo4j** (Hunters + Contributions)

The core workflow is implemented in these files:

- `main.py`: CLI entrypoint/orchestration
- `get_users.py`: leaderboard → usernames
- `profile_scraper.py`: username → profile data
- `export_csv.py`: profile data → CSV (Neo4j-friendly)

### How it works (high level)

1. Open a HackerOne leaderboard URL and extract usernames from the page.
2. For each username, open `https://hackerone.com/<username>?type=user`.
3. Run JavaScript inside the page to extract fields (name, location, joined date, socials, bio, stats, etc.) plus a contributions list.
4. Export to:
   - `hackerone_hackers.csv`
   - `hackerone_contributions.csv`
   - plus a username JSON file (`hackerone_users.json`)

### Outputs

When you run `main.py`, the project writes files in the repo root:

- **`hackerone_hackers.csv`**: one row per successfully scraped user
- **`hackerone_contributions.csv`**: multiple rows per user (program contributions)
- **`hackerone_users.json`**: the list of usernames scraped from the leaderboard

Notes:
- Users that fail to scrape are skipped in CSV export (their result contains an `error` field).
- Some example output files may already exist in the repo (e.g., `*_15.csv`, `*_15.json`) from previous runs; the current code’s default filenames are the ones listed above.

### Requirements

- **Python**: 3.9+ recommended
- **Browser automation**: this code uses `seleniumbase`’s CDP-based Chrome driver (`from seleniumbase import sb_cdp`)
  - You will need a working Chromium/Chrome environment that SeleniumBase can launch
  - CAPTCHA challenges may appear depending on your IP/behavior

Dependency note (important):
- `requirements.txt` currently lists:
  - `requests`
  - `playwright`
  - `playwright-stealth`
- But the actual runtime imports in the scraping code are based on **SeleniumBase** (`seleniumbase`) and also `selenium.webdriver...` in `get_users.py`.
  - If installation fails or runtime imports error, install SeleniumBase as well (see Install).

### Install

Create a virtual environment and install dependencies.

PowerShell example:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If you hit `ModuleNotFoundError: No module named 'seleniumbase'`, install it:

```bash
pip install seleniumbase
```

If you need Selenium explicitly:

```bash
pip install selenium
```

### Usage

Run with an optional integer argument \(N\) = number of users to process.

- **Default**: if you pass no argument, it uses `5`
- **Bounds**: must be \(1 \le N \le 100\)

Examples:

```bash
python main.py
python main.py 15
python main.py 100
```

What happens:

- `get_h1_leaderboard_usernames(N)` fetches usernames from a fixed leaderboard URL (currently hard-coded in `get_users.py`)
- `scrape_h1_profiles(usernames)` scrapes each profile and returns a list of dicts
- `export_to_csv(data, "hackerone")` writes `hackerone_hackers.csv` and `hackerone_contributions.csv`
- `main.py` writes `hackerone_users.json`

### Demo (screenshots + video)
- **Screenshots**
  
RunThePr
- **Video**
  - _TODO: link to a demo video here_

### Technical details (deep dive)

### Data flow and module responsibilities

#### `main.py` orchestration

`main.py` is the entrypoint. It:

- Parses CLI arg \(N\) with:
  - default `5` if missing
  - rejects non-integers, non-positive values, and values above `100`
- Calls:
  - `get_users.get_h1_leaderboard_usernames(n)` → list of usernames
  - `profile_scraper.scrape_h1_profiles(top_users)` → list of per-user dicts
  - `export_csv.export_to_csv(each_user, "hackerone")` → CSV files
- Writes usernames to `hackerone_users.json`

#### `get_users.py` leaderboard extraction

- Opens a **specific HackerOne leaderboard** URL:
  - `https://hackerone.com/leaderboard/all_time_reputation?...`
  - (Filters like year/quarter/country/assetType are embedded in the URL.)
- Uses SeleniumBase CDP Chrome:
  - `sb = sb_cdp.Chrome(url, use_chromium=True)`
  - waits and calls `sb.solve_captcha()`
- Extracts usernames by running page JavaScript:
  - selects anchors matching `a.daisy-link.routerlink.daisy-link--black`
  - takes `innerText`
- Filters noise strings (e.g., `Log in`, `Sign up`) and de-duplicates
- Returns at most `num_users` usernames

#### `profile_scraper.py` profile scraping

For each `username`:

- Opens `https://hackerone.com/<username>?type=user`
- Uses SeleniumBase CDP Chrome and attempts CAPTCHA solving
- Scrolls down/up to trigger lazy-loaded content
- Executes a large JavaScript snippet that builds a `data` object and returns it

Fields extracted by the in-page JavaScript include:

- `name` (parsed from a `strong.text-center` element; trims anything after `(`)
- `location` (first matching helper text that isn’t “Joined …” and isn’t numeric/noise)
- `joined_date` (helper text starting with “Joined”)
- `socials` (collects unique external links in a spacing container)
- `bio` (from the “About” card)
- `thanks_count`
- “Stats” (Signal/Impact percentiles, Reputation, Rank)
- `streak_months`
- `completed_pentests`
- `vulnerabilities_found`
- `contributions` (list of rows from “Thanks” card items)

The scraper also:

- Adds `username` into the returned dict
- On exception, appends `{'username': username, 'error': str(e)}`
- Sleeps between users (`time.sleep(3)`) for politeness

#### `export_csv.py` CSV export + Neo4j import helper

Writes two CSVs:

1. `hackerone_hackers.csv`
   - One row per scraped user
   - `socials` is JSON-encoded in a single column
   - `contributions_count` is computed as `len(contributions)`
2. `hackerone_contributions.csv`
   - Multiple rows per user (one row per contribution item)

It also prints example Cypher `LOAD CSV` commands you can adapt for Neo4j.

### Extraction strategy (why JavaScript in the page)

The project primarily extracts data by executing JavaScript in the browser context (`execute_script`) rather than relying only on Selenium element queries. This is useful when:

- Content is dynamically rendered (React/virtualized tables)
- Elements are present in DOM but not “visible” for typical Selenium conditions
- You want to gather multiple fields in one pass and return a single structured object

### Anti-bot/CAPTCHA handling

Both scraping stages call `sb.solve_captcha()`. CAPTCHA handling is inherently unreliable and depends on:

- IP reputation / network environment
- Request patterns and speed
- Site-side changes

Expect occasional failures; the code will record `error` for a user if scraping fails.

### Rate limiting and politeness delays

`profile_scraper.py` includes a `time.sleep(3)` delay per user (in addition to page waits). This reduces load and may reduce bot detection.

### Data model

#### Hacker fields

Stored in the per-user dict and written to `hackerone_hackers.csv`:

- `username`
- `name`
- `location`
- `joined_date`
- `socials` (list; CSV stores JSON string)
- `bio`
- `thanks_count`
- `signal`
- `signal_percentile`
- `impact`
- `impact_percentile`
- `reputation`
- `rank`
- `streak_months`
- `completed_pentests`
- `vulnerabilities_found`
- `contributions_count` (computed)

#### Contribution fields

Each contribution row written to `hackerone_contributions.csv`:

- `username` (foreign key back to the user)
- `program`
- `valid_closed` (string like `"418/549"` when present)
- `rep`
- `rank` (numeric text)

### Neo4j import notes

- Neo4j’s `LOAD CSV` reads from the `import` directory by default. You may need to copy the generated CSVs there, or configure Neo4j accordingly.
- The printed Cypher in `export_csv.py` is a starting point; adjust node labels/relationship names to your schema.

### Known limitations

- **Fragile selectors**: CSS class names and card headings can change on HackerOne; the JS selectors may break.
- **Hard-coded leaderboard URL**: the leaderboard filters (year/quarter/country/assetType) are embedded in code and not configurable via CLI.
- **CAPTCHA/anti-bot variability**: scraping reliability depends on environment and can fail unpredictably.
- **Headless option**: `get_users.py` defines headless options but currently doesn’t pass them into SeleniumBase Chrome creation.

### Troubleshooting

- **`ModuleNotFoundError: seleniumbase`**: `pip install seleniumbase`
- **Browser fails to launch**: ensure Chrome/Chromium is installed and SeleniumBase can locate it; try running non-headless.
- **CAPTCHA blocks scraping**: slow down, run from a different network, and expect intermittent failures.
- **Empty usernames list**: the leaderboard selector may have changed; re-check `a.daisy-link.routerlink.daisy-link--black`.

### Ethics, legality, and site terms

You are responsible for complying with:

- The target site’s Terms of Service
- Robots/crawling policies (where applicable)
- Local laws and organizational policies

Use this project only for legitimate, authorized purposes and avoid excessive traffic.

### Project structure

```text
.
├─ main.py
├─ get_users.py
├─ profile_scraper.py
├─ export_csv.py
├─ requirements.txt
├─ hackerone_hackers_15.csv                # example output (may vary)
├─ hackerone_contributions-15.csv          # example output (may vary)
├─ hackerone_users_15.json                 # example output (may vary)
└─ chromedriver-win64/                     # bundled driver notices/licenses (if present)
```

---

## Русский

### Содержание (RU)

- [Что делает проект](#что-делает-проект)
- [Как это работает (в общих чертах)](#как-это-работает-в-общих-чертах)
- [Результаты (файлы на выходе)](#результаты-файлы-на-выходе)
- [Требования](#требования)
- [Установка](#установка)
- [Использование](#использование)
- [Демо (скриншоты + видео)](#демо-скриншоты--видео)
- [Технические детали (подробно)](#технические-детали-подробно)
- [Решение проблем](#решение-проблем)
- [Этика, законность и правила сайта](#этика-законность-и-правила-сайта)
- [Структура проекта](#структура-проекта)

### Техническое содержание (RU)

- [Поток данных и ответственность модулей](#поток-данных-и-ответственность-модулей)
  - [`main.py` — оркестрация](#mainpy--оркестрация)
  - [`get_users.py` — получение пользователей из лидерборда](#get_userspy--получение-пользователей-из-лидерборда)
  - [`profile_scraper.py` — сбор данных профиля](#profile_scraperpy--сбор-данных-профиля)
  - [`export_csv.py` — экспорт CSV + подсказка по Neo4j](#export_csvpy--экспорт-csv--подсказка-по-neo4j)
- [Стратегия извлечения данных (почему JS внутри страницы)](#стратегия-извлечения-данных-почему-js-внутри-страницы)
- [Антибот/капча](#антиботкапча)
- [Ограничение скорости и задержки](#ограничение-скорости-и-задержки)
- [Модель данных](#модель-данных)
  - [Поля “hacker”](#поля-hacker)
  - [Поля “contribution”](#поля-contribution)
- [Импорт в Neo4j](#импорт-в-neo4j)
- [Ограничения](#ограничения)

### Что делает проект

Этот репозиторий собирает **часть пользователей из лидерборда HackerOne**, а затем открывает их **публичные профили** и извлекает структурированные данные, чтобы сформировать:

- **Список username’ов** (из страницы лидерборда)
- **Структурированные данные профиля** для каждого пользователя
- **Два CSV** для удобного импорта в **Neo4j** (Hunters + Contributions)

Основные файлы:

- `main.py`: запуск из командной строки и общий сценарий
- `get_users.py`: лидерборд → username’ы
- `profile_scraper.py`: username → данные профиля
- `export_csv.py`: данные профиля → CSV (удобно для Neo4j)

### Как это работает (в общих чертах)

1. Открывается URL лидерборда HackerOne и извлекаются username’ы.
2. Для каждого username открывается `https://hackerone.com/<username>?type=user`.
3. В контексте страницы выполняется JavaScript, который собирает поля (имя, локация, дата регистрации, соцсети, био, статистика и т.д.) и список contributions.
4. Данные сохраняются в:
   - `hackerone_hackers.csv`
   - `hackerone_contributions.csv`
   - а также JSON со списком username’ов (`hackerone_users.json`)

### Результаты (файлы на выходе)

После запуска `main.py` в корне репозитория появятся:

- **`hackerone_hackers.csv`**: по одной строке на каждого успешно собранного пользователя
- **`hackerone_contributions.csv`**: несколько строк на пользователя (по одному contribution)
- **`hackerone_users.json`**: список username’ов из лидерборда

Примечания:
- Пользователи, для которых сбор данных завершился ошибкой, **не попадают** в CSV (их результат содержит поле `error`).
- В репозитории могут быть “примерные” файлы прошлых запусков (например, `*_15.csv`, `*_15.json`); текущий код по умолчанию пишет имена файлов, указанные выше.

### Требования

- **Python**: рекомендуется 3.9+
- **Автоматизация браузера**: код использует SeleniumBase (CDP Chrome, `from seleniumbase import sb_cdp`)
  - Нужна рабочая среда Chrome/Chromium, которую SeleniumBase сможет запускать
  - В зависимости от условий может появляться капча

Важно про зависимости:
- В `requirements.txt` сейчас указаны:
  - `requests`
  - `playwright`
  - `playwright-stealth`
- Но фактически код во время выполнения импортирует **SeleniumBase** (`seleniumbase`) и `selenium.webdriver...` в `get_users.py`.
  - Если возникнут ошибки импорта — установите SeleniumBase (см. Установка).

### Установка

Создайте виртуальное окружение и установите зависимости.

PowerShell пример:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Если увидите `ModuleNotFoundError: No module named 'seleniumbase'`:

```bash
pip install seleniumbase
```

При необходимости Selenium:

```bash
pip install selenium
```

### Использование

Запуск с необязательным целым числом \(N\) — количеством пользователей.

- **По умолчанию**: если аргумент не передан, используется `5`
- **Ограничения**: \(1 \le N \le 100\)

Примеры:

```bash
python main.py
python main.py 15
python main.py 100
```

Что происходит:

- `get_h1_leaderboard_usernames(N)` получает username’ы из фиксированного URL (сейчас захардкожен в `get_users.py`)
- `scrape_h1_profiles(usernames)` собирает данные каждого профиля и возвращает список словарей
- `export_to_csv(data, "hackerone")` пишет `hackerone_hackers.csv` и `hackerone_contributions.csv`
- `main.py` сохраняет `hackerone_users.json`

### Демо (скриншоты + видео)

Рекомендуемые пути для будущих материалов (создайте позже):

- `docs/demo/screenshots/`
  - `run-1-cli.png`
  - `output-hackers-csv.png`
  - `output-contributions-csv.png`
  - `neo4j-import.png`
- `docs/demo/video/`
  - `demo.mp4` (или ссылка)

Затем заполните этот раздел:

- **Скриншоты**
  - _TODO: вставьте скриншоты здесь_
- **Видео**
  - _TODO: добавьте ссылку на видео-демо здесь_

### Технические детали (подробно)

### Поток данных и ответственность модулей

#### `main.py` — оркестрация

`main.py`:

- Парсит аргумент \(N\):
  - если аргумента нет — берёт `5`
  - отклоняет не-целые числа, неположительные значения и значения больше `100`
- Вызывает:
  - `get_users.get_h1_leaderboard_usernames(n)` → список username’ов
  - `profile_scraper.scrape_h1_profiles(top_users)` → список словарей по пользователям
  - `export_csv.export_to_csv(each_user, "hackerone")` → CSV файлы
- Пишет список username’ов в `hackerone_users.json`

#### `get_users.py` — получение пользователей из лидерборда

- Открывает **конкретный URL лидерборда** HackerOne:
  - `https://hackerone.com/leaderboard/all_time_reputation?...`
  - (Фильтры year/quarter/country/assetType встроены прямо в URL.)
- Использует SeleniumBase CDP Chrome:
  - `sb = sb_cdp.Chrome(url, use_chromium=True)`
  - делает паузы и вызывает `sb.solve_captcha()`
- Извлекает username’ы через JavaScript внутри страницы:
  - выбирает ссылки `a.daisy-link.routerlink.daisy-link--black`
  - берёт `innerText`
- Убирает “мусор” (`Log in`, `Sign up` и т.п.), удаляет дубликаты
- Возвращает максимум `num_users` username’ов

#### `profile_scraper.py` — сбор данных профиля

Для каждого `username`:

- Открывает `https://hackerone.com/<username>?type=user`
- Запускает SeleniumBase CDP Chrome и пытается решить капчу
- Скроллит вниз/вверх, чтобы подгрузился ленивый контент
- Выполняет большой JavaScript-код, который формирует объект `data` и возвращает его

Поля, которые извлекаются (внутри JS):

- `name` (из `strong.text-center`, обрезается часть после `(`)
- `location` (по подходящему `div.daisy-helper-text`, исключая “Joined …” и шум)
- `joined_date`
- `socials` (уникальные внешние ссылки)
- `bio` (из карточки “About”)
- `thanks_count`
- “Stats” (Signal/Impact и их Percentile, Reputation, Rank)
- `streak_months`
- `completed_pentests`
- `vulnerabilities_found`
- `contributions` (строки из карточки “Thanks”)

Дополнительно:

- Добавляется `username` в результат
- При ошибке добавляется запись `{'username': username, 'error': str(e)}`
- Между пользователями есть задержка `time.sleep(3)` (вежливо к сайту)

#### `export_csv.py` — экспорт CSV + подсказка по Neo4j

Пишет два CSV:

1. `hackerone_hackers.csv`
   - 1 строка на пользователя
   - `socials` сохраняется как JSON-строка в одной колонке
   - `contributions_count` считается как `len(contributions)`
2. `hackerone_contributions.csv`
   - несколько строк на пользователя (по одному contribution)

Также печатает пример Cypher-команд `LOAD CSV` для Neo4j.

### Стратегия извлечения данных (почему JS внутри страницы)

Данные собираются в основном через выполнение JavaScript в контексте страницы (`execute_script`), а не через “классический” Selenium-поиск элементов. Это помогает, когда:

- Контент отрисовывается динамически (React/виртуализированные таблицы)
- Элемент есть в DOM, но Selenium может “не видеть” его как видимый
- Нужно собрать много полей за один заход и вернуть структурированный объект

### Антибот/капча

В обеих стадиях используется `sb.solve_captcha()`. Надёжность решения капчи зависит от:

- сети/IP
- скорости и паттерна запросов
- изменений на стороне сайта

Поэтому возможны нестабильные результаты и ошибки по отдельным пользователям.

### Ограничение скорости и задержки

В `profile_scraper.py` есть задержка `time.sleep(3)` на каждого пользователя (плюс ожидания загрузки страниц). Это снижает нагрузку и иногда помогает избегать блокировок.

### Модель данных

#### Поля `hacker`

Сохраняются для пользователя и попадают в `hackerone_hackers.csv`:

- `username`
- `name`
- `location`
- `joined_date`
- `socials` (список; в CSV — JSON-строка)
- `bio`
- `thanks_count`
- `signal`
- `signal_percentile`
- `impact`
- `impact_percentile`
- `reputation`
- `rank`
- `streak_months`
- `completed_pentests`
- `vulnerabilities_found`
- `contributions_count`

#### Поля `contribution`

Каждая строка в `hackerone_contributions.csv`:

- `username`
- `program`
- `valid_closed` (например `"418/549"`, если доступно)
- `rep`
- `rank`

### Импорт в Neo4j

- По умолчанию Neo4j читает `LOAD CSV` из директории `import`. Возможно, CSV нужно скопировать туда или настроить Neo4j.
- Cypher, который печатает `export_csv.py`, — это “шаблон”; подстройте под свою схему.

### Ограничения

- **Хрупкие селекторы**: классы/структура страницы HackerOne могут меняться — JS селекторы могут сломаться.
- **Захардкоженный URL лидерборда**: фильтры в URL сейчас не вынесены в параметры CLI.
- **Капча/антибот**: поведение зависит от окружения и может быть непредсказуемым.
- **Headless**: в `get_users.py` объявлены headless-опции, но сейчас они не передаются в запуск SeleniumBase Chrome.

### Решение проблем

- **`ModuleNotFoundError: seleniumbase`**: `pip install seleniumbase`
- **Не запускается браузер**: убедитесь, что Chrome/Chromium установлен и доступен; попробуйте запуск без headless.
- **Капча блокирует**: уменьшите скорость, меняйте сеть, ожидайте частичных ошибок.
- **Пустой список username’ов**: возможно, изменился селектор на лидерборде (`a.daisy-link.routerlink.daisy-link--black`).

### Этика, законность и правила сайта

Вы несёте ответственность за соблюдение:

- правил/Terms of Service сайта
- политик роботов/скрейпинга (если применимо)
- законов и внутренних политик организации

Используйте проект только для законных и разрешённых целей и не создавайте избыточную нагрузку.

### Структура проекта

```text
.
├─ main.py
├─ get_users.py
├─ profile_scraper.py
├─ export_csv.py
├─ requirements.txt
├─ hackerone_hackers_15.csv                # пример результата (может отличаться)
├─ hackerone_contributions-15.csv          # пример результата (может отличаться)
├─ hackerone_users_15.json                 # пример результата (может отличаться)
└─ chromedriver-win64/                     # уведомления/лицензии драйвера (если есть)
```

