---
name: scraper
description: Scrapuje tweety z X (Twitter) przez Apify i generuje dzienny raport po polsku w tweets/{data}.md oraz skondensowany skrót w digest/{data}.md. Używaj, gdy użytkownik prosi o pobranie tweetów, scraping X, nowe tweety, dzienny raport lub skrót.
---

# scraper

> [!IMPORTANT]
> **RAPORT MUSI BYĆ W CAŁOŚCI PO POLSKU.** Sekcja „Co to znaczy" musi mieć **3-4 pełne zdania** — bez sztucznego dopychania objętości. To najczęstszy błąd agentów.

Autorytatywny opis workflow. Parametry uruchomienia (frazy, próg polubień) są zdefiniowane w `.claude/CLAUDE.md` → sekcja „Parametry kanoniczne" i zaszyte jako domyślne w `scrape.py`. **Nie powtarzaj ich tutaj — wołaj skrypt bez flag.**

## Krok 1: Data i konfiguracja

```bash
date +%Y-%m-%d
```

Sprawdź, czy istnieje `.env` z `APIFY_API_TOKEN` (szablon: `config.example.env`). Brak tokena → poproś użytkownika, nie zgaduj.

## Krok 2: Scraping (TYLKO RAZ, wszystkie frazy naraz)

Domyślne frazy i próg polubień:

```bash
cd /Users/p/Documents/dev/Web-Scraping && source venv/bin/activate && python scrape.py
```

Jeśli użytkownik podał własne frazy — wszystkie w jednym `-q`:

```bash
cd /Users/p/Documents/dev/Web-Scraping && source venv/bin/activate && python scrape.py -q "fraza A" "fraza B"
```

> Nigdy nie uruchamiaj skryptu osobno dla każdej frazy — każde wywołanie nadpisuje `raw/{data}.md` i zostaje tylko ostatnia fraza.

Wynik: `raw/{YYYY-MM-DD}.md` (surowe dane po angielsku).

## Krok 3: Raport po polsku

Przeczytaj `raw/{YYYY-MM-DD}.md` (data z kroku 1) i **utwórz nowy plik** `tweets/{YYYY-MM-DD}.md`:

```markdown
# Web Scraping - X Tweets

*Data pobrania: YYYY-MM-DD HH:MM*

## Podsumowanie

[3-4 zdania o tym, co ciekawego dzieje się w trendach — po polsku.]

---

## [Fraza]

*Pobrano: YYYY-MM-DD HH:MM*

### @użytkownik
**Nazwa** | Data: [data oryg.] | ❤️ Polubienia: [n] | 🔁 [n] | 👁 [n]

[Treść tweeta przetłumaczona w całości na polski]

> **Co to znaczy:** [3-4 PEŁNE ZDANIA o praktycznym znaczeniu wpisu dla programisty — co z tego wynika i jak wykorzystać narzędzie w codziennej pracy. Bez ogólników i bez naciągania długości: jeśli tweet to luźny komentarz albo żart bez realnej treści, napisz krótko, zamiast dopychać zdaniami-wypełniaczami.]

[Link do tweeta](URL)

---
```

### Zasady

- **Język**: cały plik po polsku, poza nazwami własnymi i datami systemowymi.
- **Zero znaków CJK**: żadnych chińskich/japońskich znaków w polskim tekście. Modele potrafią wstawić `潜在`, `因为`, `数据分析` w środek zdania — to nawracający błąd, wykryty w 10 raportach. Wyjątek: nazwy własne (np. japoński nick autora tweeta). Kontrola przed commitem:
  ```bash
  grep -P '[\x{4e00}-\x{9fff}]' tweets/$(date +%F).md
  ```
- **Tweety oznaczone ⚠️**: skrypt wstawia do `raw/` blok `> ⚠️ **Możliwa reklama** (powód)` przy wpisach z poszlakami. **Twoja decyzja, nie automat** — oceń treść i albo pomiń tweet, albo włącz go do raportu. Sam znacznik ⚠️ i powód **nigdy nie trafiają do `tweets/`**.
  - Pomijaj: lead magnet („skomentuj X, a wyślę Ci szablon", „DM po dostęp"), niepotwierdzone statystyki podparte wezwaniem do akcji, wpisy bez treści poza obietnicą.
  - Zostawiaj: kuratorowane listy repo/skilli z konkretnymi nazwami i linkami — sama liczba linków to nie reklama. Podobnie „follow me for more" doklejone na końcu merytorycznego wpisu.
- **Twierdzenia bez źródła — POMIJAJ**: skrypt wycina większość takich wpisów już na etapie `raw/`, ale regex łapie wzorce, nie sens. Jeśli w `raw/` trafisz na tweet, który **podaje coś jako fakt, a nie wskazuje źródła** — nie umieszczaj go w raporcie i nie opisuj go jako niezweryfikowany. Użytkownik nie chce czytać wpisu tylko po to, żeby dowiedzieć się, że nie wiadomo, czy to prawda.
  - Pomijaj: sensacyjne doniesienia bez linku do źródła, plotki („podobno", „krążą pogłoski"), relacje z drugiej ręki o cudzych działaniach, spektakularne liczby bez odniesienia do raportu czy pomiaru, wpisy, przy których napisałbyś „traktuję to jako niezweryfikowaną plotkę".
  - Zostawiaj: wpisy autora mówiącego o **własnej** pracy lub narzędziu (autor jest źródłem), oficjalne ogłoszenia firm, opinie i komentarze jawnie podane jako opinia, poradniki i wpisy techniczne — one niczego nie twierdzą o świecie.
  - Test: czy komentarz w sekcji „Co to znaczy" musiałby zawierać zastrzeżenie o wiarygodności? Jeśli tak — tweet nie wchodzi do raportu.
  - Blok `> 🔴 **Twierdzenie bez źródła**` w `raw/` (pojawia się tylko przy `--keep-unverified`) oznacza taki wpis wprost. Domyślnie go pomijasz; sam znacznik 🔴 **nigdy nie trafia do `tweets/`**.
- **Weryfikacja pozostałych**: filtry łapią wzorce, nie sens. Cokolwiek ewidentnie spoza IT (UFO, ezoteryka, pseudonauka) pomiń, nawet bez ⚠️.
- **Jeden raport na dzień**: `tweets/{YYYY-MM-DD}.md`, nie twórz wielu raportów (skrót powstaje osobno, w kroku 4).
- **Deduplikacja**: duplikaty ID odsiewa skrypt (`seen_tweets.json`) — nie sprawdzaj tego ręcznie. Możesz natomiast pominąć wpis, który powtarza temat już opisany w poprzednich raportach i nie wnosi nowej informacji (np. kolejna reakcja na ten sam produkt).

## Krok 4: Skrót (digest/{data}.md)

Na podstawie wpisów, które trafiły do `tweets/{YYYY-MM-DD}.md` w kroku 3 — **ta sama selekcja, nie oceniaj ponownie reklam ani źródeł** — utwórz `digest/{YYYY-MM-DD}.md`: jedną, połączoną (bez podziału na frazy), ponumerowaną listę najważniejszych wydarzeń z całego dnia, posortowaną według wagi, nie chronologii ani frazy.

```markdown
# Skrót — YYYY-MM-DD

1. Opis zdarzenia w jednym zdaniu, po polsku. (@autor) [Link](URL)
2. ...
```

### Zasady

- **Jedna linijka na pozycję** — żadnego akapitu „Co to znaczy", żadnego tłumaczenia pełnej treści tweeta. To kondensacja, nie kolejny raport.
- **Zawsze link do oryginalnego tweeta** — to główny sens tego pliku: szybki powrót do źródła, gdy coś wymaga głębszej analizy.
- **Maks. 12 pozycji.** Źródłem jest `tweets/{data}.md` — wybierz z niego wpisy o największej wadze (premiery produktów, zmiany cen/limitów, bezpieczeństwo, istotne opinie uznanych osób). Pomiń drobne anegdoty i czysto rozrywkowe wpisy, nawet jeśli są w pełnym raporcie.
- **Kolejność = ranking wagi**, nie kolejność z `tweets/` ani podział na frazy Claude Code / Codex.
- **Zero znaków CJK** — ta sama kontrola co w `tweets/`:
  ```bash
  grep -P '[\x{4e00}-\x{9fff}]' digest/$(date +%F).md   # musi nic nie zwrócić
  ```

## Krok 5: Commit i push

Push jest obowiązkowy — użytkownik czyta raporty z aplikacji Git na telefonie.

```bash
cd /Users/p/Documents/dev/Web-Scraping && git add -A && \
  git commit -m "tweets YYYY-MM-DD: <3-5 słów o głównych trendach>" && git push
```

## Krok 6: Podsumowanie w czacie

Po pushu pokaż użytkownikowi krótkie podsumowanie: ile tweetów, jakie trendy, ścieżka do pełnego raportu i ścieżka do skrótu.
