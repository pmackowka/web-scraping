# Web Scraping

Dzienny scraping tweetów z X (Twitter) przez Apify API + raport po polsku z komentarzem „co to znaczy" do każdego wpisu.

## Instalacja

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp config.example.env .env        # wklej token z https://console.apify.com/settings
```

> Zawsze aktywuj venv przed uruchomieniem (`source venv/bin/activate`). Token trzymamy wyłącznie w `.env` — nigdy w plikach repo ani w promptach.

## Użycie

```bash
source venv/bin/activate
python scrape.py                              # domyślne frazy i próg
python scrape.py -q "AI" "MCP" -l 300         # własne frazy
```

Wynik trafia do dwóch folderów na poziomie roota repo:

- `raw/{YYYY-MM-DD}.md` — surowe dane po angielsku (etap 1)
- `tweets/{YYYY-MM-DD}.md` — **raport końcowy**, po polsku, z komentarzami (etap 2, robi go agent)

### Parametry `scrape.py`

| Flaga | Opis | Domyślnie |
|-------|------|-----------|
| `-q` | Frazy wyszukiwania (wiele naraz, oddzielone spacją) | `"Claude Code" "Codex"` |
| `-m` | Maksymalna liczba tweetów na frazę | 10 |
| `-t` | Typ wyników: `Top` lub `Latest` | Top |
| `-l` | Minimalna liczba polubień | 800 |
| `-d` | Okno świeżości w dniach (dokleja `since:` do zapytania), 0 wyłącza | 7 |
| `--no-api-filter` | Nie doklejaj `min_faves:` do zapytania X (fallback przy zbyt małej liczbie wyników) | wyłączone |
| `--keep-unverified` | Nie usuwaj twierdzeń bez źródła — oznacz je 🔴 w `raw/` i zostaw ocenę agentowi | wyłączone |

> **Wszystkie frazy w jednym wywołaniu `-q`.** Osobne uruchomienia tego samego dnia nadpisują `raw/{data}.md` — zostaje tylko ostatnia fraza. Przebieg bez nowych tweetów **nie kasuje** istniejącego pliku.

**Filtry:** próg polubień trafia wprost do zapytania X (`min_faves:`), więc odpada koszt pobierania wyników, które i tak odpadną. Dalej `classify_tweet` przyznaje każdemu tweetowi werdykt:

| Werdykt | Co się dzieje |
|---------|---------------|
| `reject` | Wypada z `raw/`. Reklama, job spam, brak frazy, ucięty retweet, treść spoza IT, twierdzenie bez źródła |
| `flag` | Zostaje, ale dostaje `⚠️ Możliwa reklama` — agent ocenia w kroku 2 |
| `unverified` | Tylko przy `--keep-unverified`: zostaje z adnotacją `🔴 Twierdzenie bez źródła` |
| `ok` | Wchodzi bez adnotacji |

Odrzucenia lądują w logu z powodem. Trzy poszlaki naraz (np. dużo linków + „save this list" + „subscribe to my") dają odrzucenie; pojedyncza tylko flagę — sama liczba linków nie świadczy o reklamie, bo kuratorowane listy repo są wartościowe. Duplikaty odsiewa `seen_tweets.json` (ostatnie 10 000 ID).

**Twierdzenia bez źródła** wypadają domyślnie: sensacja podana jako fakt bez wskazania źródła (`reportedly`, `sources say`, `rumor`, nagłówek `BREAKING:`, 🚨 razem z drugą poszlaką) oraz każdy temat spoza IT podany jako news (rakiety, terroryzm, szpiegostwo). Konta z `PRIMARY_SOURCE_ACCOUNTS` — OpenAI, Anthropic i ich pracownicy mówiący o własnym narzędziu — są źródłem pierwotnym i filtr ich nie dotyczy. Ograniczenie: X skraca każdy link do `t.co`, także obrazki, więc „ma link" nie świadczy o źródle i filtr stoi wyłącznie na języku wpisu. Konsekwencja: news branżowy z drugiej ręki też wypada — `--keep-unverified` to odwraca. Szczegóły i kalibracja: [`.claude/CLAUDE.md`](.claude/CLAUDE.md).

## 🚀 Gotowce — skopiuj, wklej, gotowe

Pełny przebieg: scraping → raport po polsku → commit → push. Nic więcej nie trzeba dopisywać.

### Claude Code

```
/scrape
```

### OpenCode / Codex

```
Korzystając ze skilla `scraper` (/Users/p/Documents/dev/Web-Scraping/.claude/skills/scraper/SKILL.md), pobierz nowe tweety z serwisu X dla domyślnych fraz. Raport w języku polskim zapisz w /Users/p/Documents/dev/Web-Scraping/tweets/. Po zapisaniu plików dodaj je do repozytorium git, zrób commit i push do GitHuba.
```

### Własne frazy (dowolne narzędzie)

```
Korzystając ze skilla `scraper` (/Users/p/Documents/dev/Web-Scraping/.claude/skills/scraper/SKILL.md), pobierz nowe tweety z serwisu X dla fraz [Claude Code, MCP, dbt]. Raport w języku polskim zapisz w /Users/p/Documents/dev/Web-Scraping/tweets/. Po zapisaniu plików dodaj je do repozytorium git, zrób commit i push do GitHuba.
```

### Sam scraping, bez raportu (terminal)

```bash
cd /Users/p/Documents/dev/Web-Scraping && source venv/bin/activate && python scrape.py
```

Daje tylko surowy `raw/{data}.md` po angielsku — tłumaczenie i komentarze robi agent.

## Setup multi-agent (Claude Code / Codex / OpenCode)

Jeden schemat obsługuje trzy agenty, bez duplikowania treści — realne pliki leżą w `.claude/`, reszta to symlinki:

```
AGENTS.md → .claude/CLAUDE.md      # SYMLINK  (czyta: Codex, OpenCode)
.claude/CLAUDE.md                  # ★ REALNY — źródło prawdy o parametrach
.claude/skills/scraper/SKILL.md    # ★ REALNY — workflow (czyta: Claude Code, OpenCode)
.claude/commands/scrape.md         # slash /scrape — wrapper na skill
.agents/skills → ../.claude/skills # SYMLINK  (czyta: Codex)
```

**Nie twórz `CLAUDE.md` w rootcie** — Claude Code wczytałby schemat dwa razy. Szczegóły i uzasadnienie: [`.claude/CLAUDE.md`](.claude/CLAUDE.md).
