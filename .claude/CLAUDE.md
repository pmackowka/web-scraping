# CLAUDE.md

Dzienny scraping tweetów z X (Apify) + raport po polsku. Ten plik jest jedynym źródłem prawdy o parametrach uruchomienia.

## Kto co czyta (setup multi-agent)

```
Web-Scraping/
├── AGENTS.md → .claude/CLAUDE.md      # SYMLINK  (czyta: Codex, OpenCode)
├── .claude/
│   ├── CLAUDE.md                      # ★ REALNY — ten plik
│   ├── skills/scraper/SKILL.md        # ★ REALNY  (czyta: Claude Code, OpenCode)
│   └── commands/scrape.md             # slash /scrape — cienki wrapper na skill
└── .agents/
    └── skills → ../.claude/skills     # SYMLINK  (czyta: Codex)
```

Reguła: `.claude/` = pliki realne, `AGENTS.md` i `.agents/` = same wskaźniki. Edycja `.claude/CLAUDE.md` natychmiast zmienia `AGENTS.md` — to ten sam i-node, nie ma czego synchronizować.

> **NIE twórz `CLAUDE.md` w rootcie repo.** Claude Code wczytałby schemat dwa razy (root + `.claude/`). Uwaga na `/init`. Kontrola: `ls CLAUDE.md` musi zwracać „No such file".

Uwaga: konfiguracja (uprawnienia, MCP) **nie jest** współdzielona między narzędziami — symlinki obejmują tylko instrukcje i skille.

## Parametry kanoniczne

Dwie frazy, jedno wywołanie, próg 800 polubień:

```bash
cd /Users/p/Documents/dev/Web-Scraping && source venv/bin/activate && \
  python scrape.py -q "Claude Code" "Codex" -m 10 -t Top -l 800 -d 7
```

To są też domyślne wartości w `scrape.py` — samo `python scrape.py` daje ten sam efekt. Jeśli zmieniasz frazy lub próg, zmień je **tutaj i w `scrape.py`**; skill i komenda odsyłają do tego pliku, nie powtarzają wartości.

| Flaga | Znaczenie | Domyślnie |
|-------|-----------|-----------|
| `-q` | Frazy (wiele naraz, oddzielone spacją) | `"Claude Code" "Codex"` |
| `-m` | Maks. tweetów na frazę | 10 |
| `-t` | `Top` lub `Latest` | Top |
| `-l` | Minimalna liczba polubień | 800 |
| `-d` | Okno świeżości w dniach (`since:` w zapytaniu), 0 wyłącza | 7 |
| `--no-api-filter` | Nie doklejaj `min_faves:` do zapytania X | wyłączone |
| `--keep-unverified` | Nie usuwaj twierdzeń bez źródła — oznacz je 🔴 w `raw/` | wyłączone |

> **Wszystkie frazy w jednym wywołaniu `-q`.** Osobne uruchomienia tego samego dnia nadpisują `raw/{data}.md` — zostanie tylko ostatnia fraza.

## Data bieżąca

Sprawdź przed startem: `date +%Y-%m-%d`. Nazwy plików (`raw/{YYYY-MM-DD}.md`, `tweets/{YYYY-MM-DD}.md`) muszą używać dzisiejszej daty — inaczej agent czyta inny plik, niż skrypt zapisał.

## Środowisko

`source venv/bin/activate` przed każdą pracą. Wymagany `.env` z `APIFY_API_TOKEN` (szablon: `config.example.env`) — bez tokena skrypt kończy się błędem. Token trzymamy wyłącznie w `.env`; nigdy nie wklejaj go do plików w repo ani do promptów.

## Struktura folderów

Dwa foldery na poziomie roota repo (nie zagnieżdżone w `output/` — jedna ścieżka mniej do kliknięcia w apce Git na telefonie):

```
raw/{YYYY-MM-DD}.md      # surowe dane po angielsku (etap 1, scrape.py)
tweets/{YYYY-MM-DD}.md   # raport po polsku (etap 2, robi go agent)
```

Nazwa pliku to sama data — folder już mówi, czy to dane surowe czy gotowy raport.

> Data jako nazwa pliku sortuje chronologicznie, ale alfabetycznie rosnąco = najnowszy plik na **dole** listy, nie na górze. Jeśli aplikacja Git na telefonie nie ma opcji sortowania „ostatnio zmienione", to obecnie jedyny sposób na najnowszy raport na górze.

## Dwuetapowy pipeline

1. `scrape.py` → `raw/{data}.md` — surowe dane po angielsku
2. Skill `scraper` (`.claude/skills/scraper/SKILL.md`) → `tweets/{data}.md` — tłumaczenie + komentarze po polsku

**Skill jest autorytatywnym opisem workflow — przeczytaj go przed generowaniem raportu.**

## Język — POLSKI

Wszystkie pliki `tweets-*.md` po polsku (poza nazwami własnymi i datami systemowymi). Sekcja „Co to znaczy" musi mieć **3-4 pełne zdania**, bez sztucznego dopychania objętości na tweetach bez realnej treści. To najczęstszy błąd agentów.

**Zero znaków CJK w polskim tekście.** Modele wstawiają chińskie słowa w środek zdania (`潜在nie`, `warto密切关注`, `czy数据分析`) — znaleziono to w 10 raportach i naprawiono 2026-07-14. Sprawdź przed commitem:

```bash
grep -P '[\x{4e00}-\x{9fff}]' tweets/$(date +%F).md   # musi nic nie zwrócić
```

## Deduplikacja i filtry

- `seen_tweets.json` przechowuje ID tweetów z poprzednich uruchomień, przycinane do `MAX_SEEN_IDS` (10 000) najnowszych. `.gitignore` blokuje `*.json`, ale ten plik jest tracked — nie dodawaj innych JSON-ów do repo.
- Próg polubień leci **do zapytania X** jako `min_faves:` — actor liczy za każdy zwrócony wynik, więc filtrowanie przed pobraniem jest tańsze. `--no-api-filter` wyłącza, gdy X zwraca zbyt mało wyników.
- `classify_tweet` wymaga **dosłownego** wystąpienia frazy w treści tweeta (case-insensitive) — świadoma decyzja: zero fałszywych pozytywów kosztem części trafień.
- `EXCLUDE_WORDS` odrzuca tweety spoza IT. Nowy fałszywy pozytyw → dopisz frazę do listy.

### Trzy werdykty zamiast listy fraz

`classify_tweet` zwraca `ok` / `flag` / `reject`. Powód odrzucenia ląduje w logu — bez tego nie da się kalibrować filtrów.

| Mechanizm | Działanie |
|-----------|-----------|
| `HARD_REJECT_PATTERNS` | Pewna reklama, job spam, `apply now`. Tweet nie trafia do `raw/` |
| Ucięty retweet | `RT @kto: …` bez pełnej treści — odrzucany |
| `SOFT_FLAG_PATTERNS` | Poszlaki. Tweet zostaje, dostaje ⚠️ w `raw/` do oceny agenta |
| `SOFT_SIGNALS_FOR_REJECT` | **3+ poszlaki naraz** = pewna reklama → odrzucenie |

**Regexy, nie dosłowne frazy** — marketerzy wstawiają słowo-hasło w środek: `reply "motion" and i'll send` nie pasowało do sztywnego `reply and i'll send`. Tekst przechodzi przez `normalize_text` (X zwraca apostrof `’`, nie `'` — wzorce ASCII bez tego nie trafiały).

> **Liczba linków sama w sobie nie znaczy reklamy.** Backtest wyciął nią dwa wartościowe wpisy (22 skille do Claude Code, zestaw skilli STE — oba to listy repo GitHub). Liczy się dopiero razem z innymi poszlakami.

### Twierdzenia bez źródła

Sensacja podana jako fakt, bez linku do źródła i bez konta będącego stroną w sprawie, **nie trafia do `raw/`**. Powód: czytanie wpisu po to, żeby dowiedzieć się z komentarza agenta, że nie wiadomo, czy to prawda, jest stratą czasu.

| Mechanizm | Działanie |
|-----------|-----------|
| `OFFTOPIC_CLAIM_PATTERNS` | Temat spoza IT podany jako news (Huti, rakiety, terroryzm, szpiegostwo). Odrzucany **zawsze**, także przy `--keep-unverified` |
| `UNSOURCED_HARD_PATTERNS` | Autor sam przyznaje, że nie wie: `reportedly`, `sources say`, `rumor`, `allegedly`, nagłówek `BREAKING:`. Jedno trafienie = odrzucenie |
| `UNSOURCED_SOFT_PATTERNS` | Poszlaki: 🚨, `just in`, `apparently`, `users are reporting`, `huge news`. **2+ naraz** = odrzucenie |
| `PRIMARY_SOURCE_ACCOUNTS` | Konta oficjalne (OpenAI, Anthropic, ich pracownicy o własnym narzędziu) — filtr ich nie dotyczy, bo są źródłem pierwotnym |

> **Ograniczenie, które trzeba znać.** X skraca każdy link do `t.co`, także obrazki i cytowane tweety — z treści nie da się odróżnić linku do źródła od zdjęcia. Dlatego filtr stoi wyłącznie na języku wpisu, nie na obecności linku. Konsekwencja: news branżowy relacjonowany z drugiej ręki (afera Buckmaster/OpenAI, doniesienia o cięciu limitów Codeksa) też wypada. To świadomy wybór — `--keep-unverified` go odwraca bez edycji kodu.

Nową kategorię odrzuceń widać w logu jako `bez źródła:` albo `sensacja spoza IT:`.

Zmieniasz wzorce → puść backtest na `raw/` z historii: musi łapać znane reklamy i **nie ruszać** tweetów, które trafiły do `tweets/`. Stan na 2026-09-12: filtr twierdzeń bez źródła usuwa 11 z 413 wpisów historycznych, w tym wszystkie 4 clickbaity „BREAKING NEWS!".

## Auto-push do remote

Po utworzeniu plików w `raw/` lub `tweets/` **zawsze**: `git add -A`, commit z opisem, `git push`. Użytkownik czyta raporty z aplikacji Git na telefonie — bez pusha raport dla niego nie istnieje. Dotyczy też zmian w tym pliku, `SKILL.md`, `README.md` i `scrape.py`.

## Czego nie ma

Brak testów, lintowania, formatowania, typechecka i CI. Nie próbuj uruchamiać `pytest`, `ruff`, `black` itp.
