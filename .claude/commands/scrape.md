# scrape

Pobierz nowe tweety z X i wygeneruj dzienny raport po polsku.

Wykonaj workflow opisany w skillu `scraper` (`.claude/skills/scraper/SKILL.md`) — to autorytatywne źródło procedury: scraping → raport po polsku → skrót → commit → push.

Parametry uruchomienia (frazy, próg polubień) są w `.claude/CLAUDE.md` → „Parametry kanoniczne" i jako domyślne w `scrape.py`. Jeśli użytkownik podał w wywołaniu własne frazy, użyj ich zamiast domyślnych: $ARGUMENTS

> **Nie powielaj tu parametrów ani formatu raportu.** Ten plik celowo jest cienkim wrapperem — rozjazd między komendą, skillem i CLAUDE.md był głównym źródłem błędów w tym repo.
