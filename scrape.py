#!/usr/bin/env python3
"""
Web Scraper - pobiera tweety z X (Twitter) używając Apify API.
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    from apify_client import ApifyClient
    from dotenv import load_dotenv
except ImportError:
    print("❌ Brak zależności. Aktywuj venv i zainstaluj pakiety:")
    print("   source venv/bin/activate && pip install -r requirements.txt")
    sys.exit(1)

load_dotenv()

ACTOR_ID = "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"
RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(exist_ok=True)
SEEN_TWEETS_FILE = Path(__file__).parent / "seen_tweets.json"
# Ile ID trzymamy w historii deduplikacji (~pół roku przy obecnym tempie)
MAX_SEEN_IDS = 10000

# Domyślne frazy — źródło prawdy opisane w .claude/CLAUDE.md ("Parametry kanoniczne")
DEFAULT_KEYWORDS = ["Claude Code", "Codex"]

# Odrzuca tweety spoza kontekstu IT. Porównanie case-insensitive.
# "disclosure" celowo usunięte — łapało security-tweety o responsible disclosure.
EXCLUDE_WORDS = [
    "ufo",
    "extraterrestrial",
    "alien",
    "aliens",
    "area 51",
    "redstone arsenal",
]

# --- Filtr treści bezużytecznych ---------------------------------------------
#
# Dwa poziomy zamiast jednej listy dosłownych fraz:
#   HARD_REJECT_PATTERNS — pewniaki, skrypt wywala tweet bez pytania.
#   SOFT_FLAG_PATTERNS   — poszlaki, tweet zostaje, ale dostaje ⚠️ w raw/.
#
# Powód rozdziału: "follow me for more" pojawiło się w wartościowym tweecie
# o Taste Skill (2026-08-02) — twarde odrzucenie wycięłoby realną treść.
# Sygnały jednoznaczne ("must follow so i can dm") takiego ryzyka nie mają.
#
# Regexy, nie dosłowne frazy — marketerzy wstawiają słowo-hasło w środek:
# `reply "motion" and i'll send it over` nie pasowało do "reply and i'll send".

# Pewna reklama / lead magnet — tweet nie trafia do raw/ w ogóle.
HARD_REJECT_PATTERNS = [
    # "rt + reply 'motion' and i'll send it over", "comment X and I'll dm you"
    r"\b(reply|comment|rt|repost)\b[^.\n]{0,40}\b(and|then)\b[^.\n]{0,25}i'?ll\s+(send|dm|share|give|drop)",
    # "must be following so i can dm" — najsilniejszy pojedynczy sygnał
    r"\bmust\s+(be\s+)?follow(ing)?\b[^.\n]{0,40}\bdm\b",
    r"\bi'?ll\s+(send|dm)\s+(you|it|them)\b[^.\n]{0,30}\b(over|the|link|guide|template|prompt)\b",
    r"\bdm\s+me\s+(the\s+word|for\s+the|and\s+i)\b",
    r"\bcomment\s+[\"']\w+[\"']\s*(and|below|to\s+get)\b",
    r"\blink\s+in\s+bio\b",
    # Job spam — ogłoszenia rekrutacyjne, zero treści technicznej
    r"\b(is|are|we'?re)\s+hiring\b",
    r"\b\d+\s+open\s+roles?\b",
    r"\bapply\s+now\b",
]

# Ucięty retweet: "RT @kto: początek treści…" — API zwraca urwaną treść,
# raport z 2026-08-03 musiał to opisać jako "dalsza treść niedostępna".
# Osobny warunek, nie regex: kropka w regexie nie przechodzi przez \n,
# a wielokropek stoi w ostatniej linii, nie w tej z "RT @".
_TRUNCATED_RT_RE = re.compile(r"^rt\s+@\w+:", re.IGNORECASE)

# Poszlaki — pojedyncza nie dyskwalifikuje, dopiero kilka naraz (patrz niżej).
SOFT_FLAG_PATTERNS = [
    r"\bsave\s+this\s+(list|and|before|post|thread)\b",
    r"\bsubscribe\s+to\s+my\b",
    r"\bfollow\s+me\s+for\s+more\b",
    r"\bbookmark\s+this\b",
    r"\bworth\s+bookmarking\b",
    r"\bquietly\s+print\s+money\b",
    r"\b(share|repost)\s+(this|it)\s+(with|by|if)\b",
    r"\bnever\s+hit\s+(usage\s+)?limits\b",
    r"\bthree\s+dots,?\s+top\s+right\b",
]

# Sama liczba linków NIE świadczy o reklamie — backtest wyciął nią dwa dobre
# wpisy (@Suryanshti777: 22 skille z repo GitHub, @andrew_n_carr: skille STE).
# Liczy się dopiero w sumie z innymi poszlakami.
MANY_LINKS = 6

# Ile poszlak razem oznacza pewną reklamę. @rubenhassid miał cztery
# (18 linków + "save this list" + "subscribe to my" + "share it with a friend"),
# każdy wartościowy wpis z historii — najwyżej jedną.
SOFT_SIGNALS_FOR_REJECT = 3

# --- Filtr twierdzeń bez źródła ----------------------------------------------
#
# Problem: tweety typu "🚨 BREAKING: DeepSeek potajemnie przekierowuje zapytania
# do Claude" albo "Huti odpalają rakiety przez Claude Code" zbierają dziesiątki
# tysięcy polubień i lądowały w raporcie, gdzie agent opisywał je jako
# niezweryfikowane. Czytanie takiego wpisu po to, żeby dowiedzieć się, że nie
# wiadomo, czy to prawda, to strata czasu — filtrujemy przed raportem.
#
# Ograniczenie, które trzeba znać: X skraca KAŻDY link do t.co, także obrazki
# i cytowane tweety. Nie da się z treści odróżnić linku do źródła od zdjęcia,
# więc "ma link" nie jest sygnałem wiarygodności. Zostaje sam język wpisu.
#
# Wyłącznik: `--keep-unverified` nie usuwa tweeta, tylko oznacza go 🔴 w raw/
# i zostawia decyzję agentowi (tak działał ten pipeline przed 2026-09-12).

# Temat spoza IT podany jako news — odrzucamy zawsze, niezależnie od flagi.
# Frazy dwuwyrazowe tam, gdzie pojedyncze słowo ma sens w IT: samo
# "intelligence" to artificial intelligence, samo "strike" to strajk.
OFFTOPIC_CLAIM_PATTERNS = [
    r"\bhouthis?\b",
    r"\b(hezbollah|hamas|isis|al[- ]qaeda)\b",
    r"\bballistic\s+missiles?\b",
    r"\b(air|drone)\s?strikes?\b",
    r"\bterroris(t|m)\b",
    r"\bwar\s+crimes?\b",
    r"\bnuclear\s+weapons?\b",
    r"\b(intelligence|spy)\s+agenc(y|ies)\b",
    r"\bassassinat(e|ed|ion)\b",
    r"\b(drug\s+)?cartels?\b",
    r"\bmoney\s+laundering\b",
]

# Mocny sygnał relacji z drugiej ręki — jeden wystarczy do odrzucenia.
# Autor sam przyznaje, że nie wie, czy to prawda.
UNSOURCED_HARD_PATTERNS = [
    r"\breportedly\b",
    r"\bsources?\s+(say|said|tell|told|claim|confirm)\b",
    r"\brumou?r(s|ed|ing)?\b",
    r"\balleged(ly)?\b",
    r"\bunconfirmed\b",
    r"\bword\s+(is|on\s+the\s+street)\b",
    r"\bi\s+heard\s+(that|from)\b",
    r"\bno\s+official\s+(word|confirmation|statement|comment)\b",
    # Nagłówek "BREAKING NEWS" / "BREAKING:" — w 4 z 4 przypadków z historii
    # był clickbaitem, żaden nie trafił do raportu. Konta z
    # PRIMARY_SOURCE_ACCOUNTS są sprawdzane wcześniej, więc oficjalna
    # zapowiedź tym nie padnie. Dwukropek, nie samo "breaking": w zapowiedzi
    # biblioteki "breaking changes expected" to nie sensacja.
    r"\bbreaking\s+news\b",
    r"\bbreaking\s*:",
]

# Słabsze poszlaki — dopiero UNSOURCED_SIGNALS_FOR_REJECT naraz.
# "breaking" bez "news" celowo pominięte: "breaking changes expected"
# w zapowiedzi biblioteki to nie sensacja (raw/2026-09-06).
UNSOURCED_SOFT_PATTERNS = [
    r"[\U0001F6A8\u203C]",  # 🚨 ‼️ — emoji-nagłówek newsa
    r"\b(huge|big)\s+news\b",
    r"\bjust\s+in\b",
    r"\bapparently\b",
    r"\bleak(ed|s|ing)\b",
    r"\b(users?|people|everyone|they)\s+(are\s+)?(say|saying|report|reporting|claim|claiming)\b",
    r"\bclaims?\s+(that|to\s+have)\b",
    r"\bif\s+(this\s+is\s+)?true\b",
]

# Trzy poszlaki naraz = odrzucenie. Przy dwóch backtest wycinał wpisy, które
# źródło jednak miały: "🚨 HUGE NEWS: ... Anthropic just documented how it works"
# (watermark, 2026-08-11) i doniesienie o limitach Codeksa z pomiarem NerfTrack
# (2026-08-21) — oba padały wyłącznie przez oprawę graficzną nagłówka.
# Pewniaki i tak wychodzą przez UNSOURCED_HARD_PATTERNS, nie przez ten próg.
UNSOURCED_SIGNALS_FOR_REJECT = 3

# Konto będące stroną w sprawie jest źródłem pierwotnym — filtr go nie dotyczy.
# Ogłoszenie OpenAI o własnym produkcie nie jest plotką, nawet z 🚨 w nagłówku.
# Dopisuj tu wyłącznie konta oficjalne (firma / pracownik mówiący o swoim
# narzędziu), nie "zaufanych" komentatorów — inaczej lista zżera cały filtr.
PRIMARY_SOURCE_ACCOUNTS = {
    "openai",
    "openaidevs",
    "anthropicai",
    "claudeai",
    "claudedevs",
    "sama",
    "gdb",
    "kevinweil",
    "bcherny",
    "alexalbert__",
    "thsottiaux",
    "embirico",
    "catherineols",
}

_HARD_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in HARD_REJECT_PATTERNS]
_OFFTOPIC_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in OFFTOPIC_CLAIM_PATTERNS]
_UNSOURCED_HARD_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in UNSOURCED_HARD_PATTERNS]
_UNSOURCED_SOFT_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in UNSOURCED_SOFT_PATTERNS]
_SOFT_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in SOFT_FLAG_PATTERNS]
_LINK_RE = re.compile(r"https?://t\.co/\w+")


def normalize_text(text):
    """Sprowadza apostrofy i cudzysłowy typograficzne do ASCII.

    X zwraca U+2019 (’) zamiast ', więc wzorce z apostrofem ASCII nigdy
    nie trafiały — w raw/2026-08-03.md było 7 takich znaków.
    """
    return (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
    )


def check_unverified(text, username=""):
    """Szuka twierdzeń podanych jako fakt bez wskazania źródła.

    Zwraca (kategoria, powod) albo (None, ""). Kategoria to "offtopic"
    (temat spoza IT — odrzucamy zawsze) albo "unsourced" (relacja z drugiej
    ręki — odrzucamy, chyba że włączono --keep-unverified).
    """
    low = normalize_text(text).lower()

    for pattern in _OFFTOPIC_RE:
        match = pattern.search(low)
        if match:
            return "offtopic", f"sensacja spoza IT: '{match.group(0).strip()}'"

    # Konto oficjalne mówi o własnym produkcie — to źródło, nie plotka.
    if username.lower().lstrip("@") in PRIMARY_SOURCE_ACCOUNTS:
        return None, ""

    for pattern in _UNSOURCED_HARD_RE:
        match = pattern.search(low)
        if match:
            return "unsourced", f"relacja z drugiej ręki: '{match.group(0).strip()}'"

    signals = []
    for pattern in _UNSOURCED_SOFT_RE:
        match = pattern.search(low)
        if match:
            signals.append(f"'{match.group(0).strip()[:25]}'")

    if len(signals) >= UNSOURCED_SIGNALS_FOR_REJECT:
        return "unsourced", f"{len(signals)} sygnały sensacji: " + "; ".join(signals[:3])

    return None, ""


def classify_tweet(text, keyword, like_count, min_likes, username="", keep_unverified=False):
    """Ocenia pojedynczy tweet.

    Zwraca (werdykt, powód), gdzie werdykt to "ok", "flag", "unverified"
    albo "reject". Powód służy do logowania — bez niego nie da się
    kalibrować filtrów.
    """
    norm = normalize_text(text)
    low = norm.lower()

    if keyword.lower() not in low:
        return "reject", "brak frazy w treści"

    if like_count < min_likes:
        return "reject", f"za mało polubień ({like_count} < {min_likes})"

    for word in EXCLUDE_WORDS:
        if word in low:
            return "reject", f"spoza IT: '{word}'"

    stripped = norm.strip()
    if _TRUNCATED_RT_RE.match(stripped) and stripped.endswith("…"):
        return "reject", "ucięty retweet (brak pełnej treści)"

    for pattern in _HARD_RE:
        match = pattern.search(low)
        if match:
            return "reject", f"reklama: '{match.group(0)[:45].strip()}'"

    # Twierdzenia bez źródła — przed poszlakami reklamy, bo powód odrzucenia
    # ma w logu wskazywać realną przyczynę, a nie liczbę linków.
    category, unverified_reason = check_unverified(norm, username)
    if category == "offtopic":
        return "reject", unverified_reason
    if category == "unsourced":
        if not keep_unverified:
            return "reject", f"bez źródła: {unverified_reason}"
        return "unverified", unverified_reason

    flags = []
    link_count = len(_LINK_RE.findall(norm))
    if link_count >= MANY_LINKS:
        flags.append(f"{link_count} linków")
    for pattern in _SOFT_RE:
        match = pattern.search(low)
        if match:
            flags.append(f"'{match.group(0)[:30].strip()}'")

    if len(flags) >= SOFT_SIGNALS_FOR_REJECT:
        return "reject", f"reklama ({len(flags)} sygnały): " + "; ".join(flags[:3])

    if flags:
        return "flag", "; ".join(flags)

    return "ok", ""


def get_api_token():
    """Pobiera API token z zmiennej środowiskowej lub pliku .env"""
    token = os.getenv("APIFY_API_TOKEN")
    if token:
        return token

    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        token = os.getenv("APIFY_API_TOKEN")
        if token:
            return token

    print("❌ Brak API token!")
    print("   1. Wejdź na https://console.apify.com/settings")
    print("   2. Skopiuj token z sekcji 'API tokens'")
    print("   3. Wklej do pliku .env jako APIFY_API_TOKEN=...")
    sys.exit(1)


def load_seen_tweets():
    """Wczytuje ID tweetów z poprzednich uruchomień (kolejność = wiek)."""
    if SEEN_TWEETS_FILE.exists():
        try:
            return list(json.loads(SEEN_TWEETS_FILE.read_text(encoding="utf-8")))
        except Exception:
            return []
    return []


def save_seen_tweets(old_ids, new_ids):
    """Dopisuje nowe ID i przycina plik do MAX_SEEN_IDS najnowszych.

    Bez limitu plik rósłby bez końca w każdym commicie. Obcięcie starych
    jest bezpieczne: okno `since:` i tak nie sięga dalej niż kilka dni.
    """
    merged = [i for i in old_ids if i not in new_ids] + list(new_ids)
    trimmed = merged[-MAX_SEEN_IDS:]
    try:
        SEEN_TWEETS_FILE.write_text(json.dumps(trimmed), encoding="utf-8")
    except Exception as e:
        print(f"⚠️ Nie udało się zapisać seen_tweets.json: {e}")


def scrape_tweets(query, max_items=20, query_type="Top"):
    """Pobiera tweety dla danego zapytania"""
    client = ApifyClient(token=get_api_token())

    input_data = {
        "twitterContent": query,
        "maxItems": max_items,
        "queryType": query_type,
        "lang": "en",
        "include:nativeretweets": True
    }

    print(f"🔍 Szukam: '{query}' ({max_items} tweetów, {query_type})...")

    try:
        run = client.actor(ACTOR_ID).call(run_input=input_data)

        if not run or not run.get("defaultDatasetId"):
            print(f"⚠️  Brak wyników dla: {query}")
            return []

        items = list(client.dataset(run.get("defaultDatasetId")).iterate_items())

        if not items:
            print(f"⚠️  Brak wyników w datasecie dla: {query}")
            return []

        print(f"✅ Pobrano {len(items)} tweetów dla: {query}")
        return items

    except Exception as e:
        print(f"❌ Błąd podczas pobierania '{query}': {e}")
        return []


def filter_tweets(items, keyword, min_likes=20, verbose=True, keep_unverified=False):
    """Filtruje tweety przez classify_tweet i raportuje powody odrzuceń."""
    filtered = []
    rejected = []

    for item in items:
        username = item.get("author", {}).get("userName", "")
        verdict, reason = classify_tweet(
            item.get("text", ""),
            keyword,
            item.get("likeCount", 0),
            min_likes,
            username=username,
            keep_unverified=keep_unverified,
        )

        if verdict == "reject":
            rejected.append((username or "?", reason))
            continue

        item["_bait_flag"] = reason if verdict == "flag" else ""
        item["_unverified_flag"] = reason if verdict == "unverified" else ""
        filtered.append(item)

    print(f"📝 Przefiltrowano: {len(filtered)}/{len(items)} tweetów spełnia kryteria (słowo: '{keyword}', min. {min_likes} ❤️)")

    if verbose and rejected:
        # Ciche odrzucenia uniemożliwiały ocenę, czy filtr działa czy przesadza
        interesting = [(u, r) for u, r in rejected if not r.startswith(("brak frazy", "za mało"))]
        skipped = len(rejected) - len(interesting)
        for username, reason in interesting:
            print(f"   🚫 @{username}: {reason}")
        if skipped:
            print(f"   · {skipped} odrzuconych na progu polubień / braku frazy")

    flagged = [i for i in filtered if i.get("_bait_flag")]
    for item in flagged:
        print(f"   ⚠️  @{item.get('author', {}).get('userName', '?')}: {item['_bait_flag']}")

    unverified = [i for i in filtered if i.get("_unverified_flag")]
    for item in unverified:
        print(f"   🔴 @{item.get('author', {}).get('userName', '?')}: {item['_unverified_flag']}")

    return filtered


def format_to_markdown(items, keyword):
    """Konwertuje tweety do formatu Markdown"""
    if not items:
        return f"## {keyword}\n\nBrak tweetów do wyświetlenia.\n"

    md = f"## {keyword}\n\n"
    md += f"*Pobrano: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"

    for item in items:
        author = item.get("author", {})
        username = author.get("userName", "unknown")
        name = author.get("name", username)
        text = item.get("text", "")
        created_at = item.get("createdAt", "")
        like_count = item.get("likeCount", 0)
        retweet_count = item.get("retweetCount", 0)
        view_count = item.get("viewCount", 0)
        url = item.get("url", "")

        md += f"### @{username}\n"
        md += f"**{name}** | "
        md += f"Data: {created_at} | "
        md += f"❤️ Polubienia: {like_count} | "
        md += f"🔁 {retweet_count} | "
        md += f"👁 {view_count}\n\n"
        # Poszlaka reklamy — agent w kroku 3 decyduje, czy wpis trafi do raportu
        if item.get("_bait_flag"):
            md += f"> ⚠️ **Możliwa reklama** ({item['_bait_flag']}) — oceń przed włączeniem do raportu.\n\n"
        # Widoczne tylko przy --keep-unverified; normalnie takie tweety nie
        # docierają do raw/ w ogóle.
        if item.get("_unverified_flag"):
            md += f"> 🔴 **Twierdzenie bez źródła** ({item['_unverified_flag']}) — domyślnie pomijaj w raporcie.\n\n"
        md += f"{text}\n\n"
        if url:
            md += f"[Link do tweeta]({url})\n"
        md += "\n---\n\n"

    return md


def save_to_file(content, filepath):
    """Zapisuje treść do pliku pod podaną ścieżką"""
    filepath.write_text(content, encoding="utf-8")
    print(f"💾 Zapisano: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Pobieranie tweetów z X")
    parser.add_argument("-q", "--query", nargs="+", default=DEFAULT_KEYWORDS,
                      help=f"Hasła wyszukiwania, wiele naraz (default: {' '.join(DEFAULT_KEYWORDS)})")
    parser.add_argument("-m", "--max", type=int, default=10, help="Maksymalna liczba tweetów na frazę (default: 10)")
    parser.add_argument("-t", "--type", default="Top", choices=["Top", "Latest"],
                      help="Typ wyszukiwania (default: Top)")
    parser.add_argument("-l", "--likes", type=int, default=800, help="Minimalna liczba polubień (default: 800)")
    parser.add_argument("-d", "--days", type=int, default=7,
                      help="Okno świeżości w dniach — dokleja 'since:' do zapytania, 0 wyłącza (default: 7)")
    parser.add_argument("--no-api-filter", action="store_true",
                      help="Nie doklejaj 'min_faves:' do zapytania (fallback, gdy X zwraca zbyt mało wyników)")
    parser.add_argument("--keep-unverified", action="store_true",
                      help="Nie odrzucaj twierdzeń bez źródła — oznacz je 🔴 w raw/ i zostaw ocenę agentowi")

    args = parser.parse_args()

    keywords = args.query

    all_markdown = "# Web Scraping - X Tweets\n\n"
    all_markdown += f"*Data pobrania: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"

    seen_ids = load_seen_tweets()
    seen_lookup = set(seen_ids)   # lista trzyma wiek, set daje szybkie "in"
    new_seen_ids = []
    total_new = 0

    # Filtr świeżości: tryb Top bez daty zwraca stare viralowe tweety (płatne per result)
    query_suffix = ""
    if args.days > 0:
        since_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
        query_suffix += f" since:{since_date}"

    # Próg polubień po stronie X, nie po pobraniu — actor liczy za każdy zwrócony
    # wynik, a bez tego ~60% puli odpadało dopiero w filter_tweets.
    if args.likes > 0 and not args.no_api_filter:
        query_suffix += f" min_faves:{args.likes}"

    for keyword in keywords:
        items = scrape_tweets(f"{keyword}{query_suffix}", args.max, args.type)
        filtered = filter_tweets(items, keyword, args.likes, keep_unverified=args.keep_unverified)

        # Deduplikacja — tweet bez ID/URL przechodzi, ale nie trafia do seen
        unique_items = []
        for item in filtered:
            tweet_id = item.get("id") or item.get("url")
            if tweet_id and tweet_id in seen_lookup:
                continue
            unique_items.append(item)
            if tweet_id:
                new_seen_ids.append(tweet_id)
                seen_lookup.add(tweet_id)

        total_new += len(unique_items)
        markdown = format_to_markdown(unique_items, keyword)
        all_markdown += markdown

    filename = f"{datetime.now().strftime('%Y-%m-%d')}.md"
    filepath = RAW_DIR / filename

    # Pusty przebieg nie może skasować dorobku wcześniejszego uruchomienia
    if total_new == 0:
        print("\nℹ️ Nie znaleziono żadnych nowych tweetów.")
        if filepath.exists():
            print(f"   Zostawiam bez zmian: {filepath}")
            return
        print("   Nie tworzę pustego pliku.")
        return

    save_to_file(all_markdown, filepath)

    # Zapisujemy nowe ID do pliku na przyszłość
    save_seen_tweets(seen_ids, new_seen_ids)

    print(f"\n✅ Gotowe! Pobrano unikalnych: {total_new}. Wynik w: {filepath}")


if __name__ == "__main__":
    main()