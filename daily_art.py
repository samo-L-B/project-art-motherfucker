#!/usr/bin/env python3
"""
daily_art.py — a 5-minute daily intro to a great artist or photographer.

Run it with no arguments to get today's pick, drawn from BOTH the art and
photography databases. It remembers what it has already shown you (in
~/.daily_art/state.json) and won't repeat an artist until the whole pool
has been covered, then reshuffles for a new round.

Usage:
    python3 daily_art.py                        Today's artist, from art + photography combined
    python3 daily_art.py --category art          Today's artist, from the art database only
    python3 daily_art.py --category photography  Today's artist, from the photography database only
    python3 daily_art.py --random                A random artist right now (doesn't affect the daily cycle)
    python3 daily_art.py --name "Klimt"          Show a specific artist by name (partial match ok)
    python3 daily_art.py --list                  List every artist across both databases
    python3 daily_art.py --stats                 Show how many you've seen / how many remain
    python3 daily_art.py --reset                 Reset your viewing history and reshuffle
    python3 daily_art.py --data PATH             Use a single custom JSON file instead of the defaults
    python3 daily_art.py --no-color              Disable ANSI colors and hyperlinks (useful for piping to a file)

Data files (must sit next to this script, unless --data is used):
    art_data.json           Painters, printmakers, sculptors
    photography_data.json   Photographers
"""

import argparse
import json
import os
import random
import shutil
import sys
import textwrap
from datetime import date
from pathlib import Path
from urllib.parse import quote

# ---------------------------------------------------------------------------
# Paths & state
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILES = {
    "art": SCRIPT_DIR / "art_data.json",
    "photography": SCRIPT_DIR / "photography_data.json",
}

STATE_DIR = Path.home() / ".daily_art"
STATE_PATH = STATE_DIR / "state.json"

WORDS_PER_MINUTE = 130  # rough reading speed, used to show an estimated read time


# ---------------------------------------------------------------------------
# Terminal colors & hyperlinks (graceful no-op if disabled / unsupported)
# ---------------------------------------------------------------------------

class Palette:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def __call__(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"\033[{code}m{text}\033[0m"

    def bold(self, text):
        return self("1", text)

    def dim(self, text):
        return self("2", text)

    def title(self, text):
        return self("1;38;5;214", text)  # bold orange

    def heading(self, text):
        return self("1;38;5;38", text)  # bold cyan

    def accent(self, text):
        return self("38;5;250", text)

    def italic(self, text):
        return self("3", text)

    def link(self, url: str, text: str) -> str:
        """Terminal hyperlink (OSC 8). Most modern terminals (iTerm2, Windows
        Terminal, GNOME Terminal, kitty, VS Code) make this clickable. If
        colors/hyperlinks are disabled, just show the text plainly — the raw
        URL is always printed separately as a fallback."""
        if not self.enabled:
            return text
        return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.name == "nt":
        os.system("")  # enable ANSI escapes on modern Windows terminals
    return sys.stdout.isatty()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_artists_from_file(data_path: Path) -> list:
    if not data_path.exists():
        print(f"Could not find artist data file at: {data_path}")
        sys.exit(1)
    with open(data_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    artists = payload.get("artists", [])
    if not artists:
        print(f"The artist data file at {data_path} has no entries.")
        sys.exit(1)
    return artists


def load_artists(category: str, explicit_data: str = None) -> list:
    """category is one of: 'art', 'photography', 'both'. Ignored if explicit_data is set."""
    if explicit_data:
        return load_artists_from_file(Path(explicit_data))

    if category == "art":
        return load_artists_from_file(DATA_FILES["art"])
    if category == "photography":
        return load_artists_from_file(DATA_FILES["photography"])

    # both
    combined = []
    for path in DATA_FILES.values():
        if path.exists():
            combined.extend(load_artists_from_file(path))
    if not combined:
        print("Could not find art_data.json or photography_data.json next to this script.")
        sys.exit(1)
    return combined


# ---------------------------------------------------------------------------
# State management (daily rotation + history, no repeats until exhausted)
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def new_shuffled_order(names: list) -> list:
    order = names[:]
    random.shuffle(order)
    return order


def get_today_artist(artists: list, state: dict, pool_key: str) -> dict:
    """
    Returns today's artist for the given pool (e.g. 'art', 'photography', 'both').
    Each pool keeps its own independent shuffled queue and history, so switching
    --category doesn't disturb your progress in the other pool(s).
    Uses a shuffled queue of names so every artist is shown once before any
    repeats. Caches the result per calendar day so running the script multiple
    times in one day shows the same artist.
    """
    names = [a["name"] for a in artists]
    today_str = date.today().isoformat()

    pools = state.setdefault("pools", {})
    pool = pools.setdefault(pool_key, {})

    queue = pool.get("queue", [])
    if not queue or set(queue) != set(names):
        queue = new_shuffled_order(names)

    if pool.get("last_shown_date") == today_str and pool.get("last_shown_name") in names:
        chosen_name = pool["last_shown_name"]
    else:
        chosen_name = queue.pop(0)
        if not queue:
            queue = new_shuffled_order(names)
        pool["queue"] = queue
        pool["last_shown_date"] = today_str
        pool["last_shown_name"] = chosen_name
        history = pool.get("history", [])
        history.append({"date": today_str, "name": chosen_name})
        pool["history"] = history[-200:]  # keep history from growing unbounded

    return next(a for a in artists if a["name"] == chosen_name)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def term_width() -> int:
    width = shutil.get_terminal_size(fallback=(88, 24)).columns
    return max(50, min(width, 100))


def wrap(text: str, width: int, indent: str = "") -> str:
    wrapped = textwrap.wrap(text, width=width - len(indent))
    return "\n".join(indent + line for line in wrapped)


def rule(width: int, char: str = "─") -> str:
    return char * width


def estimate_minutes(artist: dict) -> int:
    fields = [artist.get("biography", ""), artist.get("style", "")]
    fields += artist.get("technical_skillset", [])
    fields += [w.get("note", "") for w in artist.get("top_works", [])]
    word_count = sum(len(f.split()) for f in fields)
    minutes = max(1, round(word_count / WORDS_PER_MINUTE))
    return minutes


def render(artist: dict, c: Palette) -> str:
    width = term_width()
    out = []

    out.append(c.title(rule(width, "═")))
    header = f"{artist['name']}  ({artist.get('years', '')})"
    out.append(c.title(header.center(width)))
    subheader = f"{artist.get('discipline', '')} · {artist.get('nationality', '')}"
    out.append(c.accent(subheader.strip(' ·').center(width)))
    out.append(c.title(rule(width, "═")))
    out.append("")

    if artist.get("intro"):
        out.append(c.italic(wrap(artist["intro"], width)))
        out.append("")

    minutes = estimate_minutes(artist)
    out.append(c.dim(f"⏱  About {minutes} minute{'s' if minutes != 1 else ''} read"))
    out.append("")

    def section(icon: str, heading: str, body_lines: list):
        out.append(c.heading(f"{icon}  {heading.upper()}"))
        out.append(c.dim(rule(min(width, len(heading) + 6), "─")))
        for line in body_lines:
            out.append(line)
        out.append("")

    section("📖", "Biography", [wrap(artist.get("biography", ""), width)])
    section("🎨", "Style", [wrap(artist.get("style", ""), width)])

    skill_lines = []
    for i, item in enumerate(artist.get("technical_skillset", []), start=1):
        skill_lines.append(
            textwrap.fill(item, width=width - 2, initial_indent=f"  {i}. ", subsequent_indent="     ")
        )
    section("🛠 ", "Technical Skillset", skill_lines)

    work_lines = []
    for item in artist.get("top_works", []):
        title = item.get("title", "")
        year = item.get("year", "")
        note = item.get("note", "")
        link_url = item.get("link", "")

        title_year = f"{title} ({year})" if year else title
        header_line = textwrap.fill(
            title_year, width=width - 4, initial_indent="  • ", subsequent_indent="    "
        )
        work_lines.append(c.bold(header_line))
        if note:
            work_lines.append(textwrap.fill(note, width=width - 6, initial_indent="    ", subsequent_indent="    "))
        if link_url:
            clickable = c.link(link_url, "View this piece →")
            work_lines.append(c.dim(f"    🔗 {clickable}"))
            if not c.enabled:
                work_lines.append(f"       {link_url}")
        work_lines.append("")
    if work_lines and work_lines[-1] == "":
        work_lines.pop()
    section("🖼 ", "Top Works", work_lines)

    out.append(c.title(rule(width, "═")))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(artists: list, c: Palette):
    print(c.heading(f"\nArtist database ({len(artists)} total)\n"))
    by_discipline = {}
    for a in artists:
        by_discipline.setdefault(a.get("discipline", "Other"), []).append(a)
    for discipline in sorted(by_discipline):
        print(c.bold(discipline))
        for a in sorted(by_discipline[discipline], key=lambda x: x["name"]):
            print(f"  • {a['name']}  ({a.get('years', '')})")
        print()


def cmd_stats(artists: list, state: dict, pool_key: str, c: Palette):
    names = {a["name"] for a in artists}
    pool = state.get("pools", {}).get(pool_key, {})
    history = pool.get("history", [])
    seen_names = {h["name"] for h in history}
    seen_in_db = seen_names & names
    print(c.heading(f"\nYour progress ({pool_key})\n"))
    print(f"  Artists in this pool : {len(names)}")
    print(f"  Distinct artists seen : {len(seen_in_db)}")
    print(f"  Remaining in this cycle : {len(pool.get('queue', []))}")
    if history:
        last = history[-1]
        print(f"  Last shown : {last['name']} on {last['date']}")
    print()


def find_by_name(artists: list, query: str):
    query_lower = query.strip().lower()
    exact = [a for a in artists if a["name"].lower() == query_lower]
    if exact:
        return exact[0]
    partial = [a for a in artists if query_lower in a["name"].lower()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        print(f"Multiple matches for '{query}':")
        for a in partial:
            print(f"  - {a['name']}")
        sys.exit(1)
    print(f"No artist found matching '{query}'. Try --list to see all names.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A 5-minute daily intro to a great artist or photographer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--category", choices=["art", "photography", "both"], default="both",
        help="Which database to draw from (default: both, combined)"
    )
    parser.add_argument("--random", action="store_true", help="Show a random artist (doesn't touch the daily cycle)")
    parser.add_argument("--name", type=str, help="Show a specific artist by name (partial match ok)")
    parser.add_argument("--list", action="store_true", help="List all artists in the selected database(s)")
    parser.add_argument("--stats", action="store_true", help="Show your viewing progress")
    parser.add_argument("--reset", action="store_true", help="Reset viewing history and reshuffle the cycle")
    parser.add_argument("--data", type=str, default=None, help="Path to a single custom artists JSON file (overrides --category)")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output and hyperlinks")
    args = parser.parse_args()

    c = Palette(enabled=(supports_color() and not args.no_color))
    artists = load_artists(args.category, explicit_data=args.data)
    pool_key = "custom:" + args.data if args.data else args.category

    if args.list:
        cmd_list(artists, c)
        return

    if args.reset:
        if STATE_PATH.exists():
            STATE_PATH.unlink()
        print("History reset. Your next run will start a fresh shuffled cycle for every pool.")
        return

    state = load_state()

    if args.stats:
        cmd_stats(artists, state, pool_key, c)
        return

    if args.name:
        artist = find_by_name(artists, args.name)
        print(render(artist, c))
        return

    if args.random:
        artist = random.choice(artists)
        print(render(artist, c))
        return

    artist = get_today_artist(artists, state, pool_key)
    save_state(state)
    print(render(artist, c))


if __name__ == "__main__":
    main()
