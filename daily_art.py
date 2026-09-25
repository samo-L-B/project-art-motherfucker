#!/usr/bin/env python3
"""
daily_art.py — Interactive daily introduction to a great artist or photographer.

Controls
========

DESCRIPTION SCREEN
    ENTER / SPACE / RIGHT / DOWN
        Open artwork list.

    Q / ESC
        Quit.

ARTWORK SCREEN
    UP / DOWN
        Select artwork.

    ENTER / SPACE / B
        Open selected artwork.

    LEFT / BACKSPACE
        Return to description.

    Q / ESC
        Quit.

The program never asks for an additional "Press ENTER to close"
input when it finishes.
"""

import argparse
import json
import os
import random
import re
import shutil
import sys
import textwrap
import webbrowser
from datetime import date
from pathlib import Path


# ============================================================================
# PATHS & STATE
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent

DATA_FILES = {
    "art": SCRIPT_DIR / "art_data.json",
    "photography": SCRIPT_DIR / "photography_data.json",
}

STATE_DIR = Path.home() / ".daily_art"
STATE_PATH = STATE_DIR / "state.json"

WORDS_PER_MINUTE = 130


# ============================================================================
# TERMINAL COLORS
# ============================================================================

class Palette:
    def __init__(self, enabled=True):
        self.enabled = enabled

    def __call__(self, code, text):
        if not self.enabled:
            return text

        return f"\033[{code}m{text}\033[0m"

    def bold(self, text):
        return self("1", text)

    def dim(self, text):
        return self("2", text)

    def title(self, text):
        return self("1;38;5;214", text)

    def heading(self, text):
        return self("1;38;5;38", text)

    def accent(self, text):
        return self("38;5;250", text)

    def italic(self, text):
        return self("3", text)

    def green(self, text):
        return self("1;32", text)

    def yellow(self, text):
        return self("1;33", text)

    def red(self, text):
        return self("1;31", text)

    def blue(self, text):
        return self("1;34", text)


def supports_color():
    if os.environ.get("NO_COLOR"):
        return False

    return sys.stdout.isatty()


# ============================================================================
# TERMINAL CONTROL
# ============================================================================

def clear_screen():
    print("\033[2J\033[H", end="", flush=True)


def hide_cursor():
    print("\033[?25l", end="", flush=True)


def show_cursor():
    print("\033[?25h", end="", flush=True)


def terminal_width():
    width = shutil.get_terminal_size(
        fallback=(100, 30)
    ).columns

    return max(60, min(width, 110))


def rule(width, char="─"):
    return char * width


def wrap_text(text, width, indent=""):
    if not text:
        return ""

    return textwrap.fill(
        str(text),
        width=max(20, width - len(indent)),
        initial_indent=indent,
        subsequent_indent=indent,
    )


# ============================================================================
# KEYBOARD INPUT
# ============================================================================

def read_key():
    """
    Read one key without requiring ENTER.

    Returns:
        ENTER
        SPACE
        UP
        DOWN
        LEFT
        RIGHT
        BACKSPACE
        ESC
        ordinary letters
    """

    if os.name == "nt":
        import msvcrt

        key = msvcrt.getwch()

        if key in ("\x00", "\xe0"):
            key2 = msvcrt.getwch()

            mapping = {
                "H": "UP",
                "P": "DOWN",
                "K": "LEFT",
                "M": "RIGHT",
            }

            return mapping.get(key2, key2)

        if key == "\r":
            return "ENTER"

        if key == " ":
            return "SPACE"

        if key == "\x08":
            return "BACKSPACE"

        if key == "\x1b":
            return "ESC"

        return key.lower()

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)

        key = sys.stdin.read(1)

        if key in ("\r", "\n"):
            return "ENTER"

        if key == " ":
            return "SPACE"

        if key == "\x7f":
            return "BACKSPACE"

        if key == "\x1b":
            next1 = sys.stdin.read(1)

            if next1 == "[":
                next2 = sys.stdin.read(1)

                mapping = {
                    "A": "UP",
                    "B": "DOWN",
                    "C": "RIGHT",
                    "D": "LEFT",
                }

                return mapping.get(next2, "ESC")

            return "ESC"

        return key.lower()

    finally:
        termios.tcsetattr(
            fd,
            termios.TCSADRAIN,
            old_settings,
        )


# ============================================================================
# DATA
# ============================================================================

def load_artists_from_file(data_path):
    if not data_path.exists():
        print()
        print("Could not find artist data file:")
        print(f"  {data_path}")
        print()
        return []

    try:
        with open(
            data_path,
            "r",
            encoding="utf-8",
        ) as f:
            payload = json.load(f)

    except (json.JSONDecodeError, OSError) as exc:
        print()
        print(f"Could not read {data_path}")
        print(exc)
        print()
        return []

    artists = payload.get("artists", [])

    if not isinstance(artists, list):
        return []

    return artists


def load_artists(category, explicit_data=None):

    if explicit_data:
        return load_artists_from_file(
            Path(explicit_data)
        )

    if category == "art":
        return load_artists_from_file(
            DATA_FILES["art"]
        )

    if category == "photography":
        return load_artists_from_file(
            DATA_FILES["photography"]
        )

    combined = []

    for path in DATA_FILES.values():
        if path.exists():
            combined.extend(
                load_artists_from_file(path)
            )

    return combined


# ============================================================================
# STATE
# ============================================================================

def load_state():

    if not STATE_PATH.exists():
        return {}

    try:
        with open(
            STATE_PATH,
            "r",
            encoding="utf-8",
        ) as f:
            return json.load(f)

    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):

    try:
        STATE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            STATE_PATH,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                state,
                f,
                indent=2,
                ensure_ascii=False,
            )

    except OSError:
        pass


def new_shuffled_order(names):
    order = names[:]
    random.shuffle(order)
    return order


def get_today_artist(
    artists,
    state,
    pool_key,
):

    names = [
        artist["name"]
        for artist in artists
    ]

    today_str = date.today().isoformat()

    pools = state.setdefault(
        "pools",
        {},
    )

    pool = pools.setdefault(
        pool_key,
        {},
    )

    queue = pool.get(
        "queue",
        [],
    )

    if not queue or set(queue) != set(names):
        queue = new_shuffled_order(names)

    if (
        pool.get("last_shown_date") == today_str
        and pool.get("last_shown_name") in names
    ):
        chosen_name = pool["last_shown_name"]

    else:
        chosen_name = queue.pop(0)

        if not queue:
            queue = new_shuffled_order(names)

        pool["queue"] = queue
        pool["last_shown_date"] = today_str
        pool["last_shown_name"] = chosen_name

        history = pool.get(
            "history",
            [],
        )

        history.append(
            {
                "date": today_str,
                "name": chosen_name,
            }
        )

        pool["history"] = history[-200:]

    for artist in artists:
        if artist["name"] == chosen_name:
            return artist

    return artists[0]


# ============================================================================
# ARTWORK HELPERS
# ============================================================================

def get_artwork_image_urls(work):

    urls = []

    for key in (
        "image",
        "image_url",
        "imageUrl",
    ):
        value = work.get(key)

        if isinstance(value, str) and value.strip():
            urls.append(value.strip())

    for key in (
        "image_urls",
        "images",
    ):
        value = work.get(key)

        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    urls.append(item.strip())

    result = []

    for url in urls:
        if url not in result:
            result.append(url)

    return result


def get_artwork_link(work):

    for key in (
        "link",
        "url",
        "page_url",
        "pageUrl",
    ):
        value = work.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def get_artwork_url(work):

    link = get_artwork_link(work)

    if link:
        return link

    images = get_artwork_image_urls(work)

    if images:
        return images[0]

    return ""


def open_url(url):

    if not url:
        return False

    try:
        return webbrowser.open(
            url,
            new=0,
            autoraise=True,
        )

    except Exception:
        return False


# ============================================================================
# TEXT
# ============================================================================

def estimate_minutes(artist):

    fields = [
        artist.get("biography", ""),
        artist.get("style", ""),
    ]

    fields += artist.get(
        "technical_skillset",
        [],
    )

    fields += [
        work.get("note", "")
        for work in artist.get(
            "top_works",
            [],
        )
    ]

    word_count = 0

    for field in fields:
        if isinstance(field, str):
            word_count += len(field.split())

    return max(
        1,
        round(word_count / WORDS_PER_MINUTE),
    )


# ============================================================================
# HEADER
# ============================================================================

def print_header(
    artist,
    c,
    screen_name,
):

    width = terminal_width()

    print(
        c.title(
            rule(width, "═")
        )
    )

    title = artist.get(
        "name",
        "Unknown Artist",
    )

    years = artist.get(
        "years",
        "",
    )

    if years:
        title = f"{title}  ({years})"

    print(
        c.title(
            title.center(width)
        )
    )

    subtitle_parts = []

    if artist.get("discipline"):
        subtitle_parts.append(
            str(artist["discipline"])
        )

    if artist.get("nationality"):
        subtitle_parts.append(
            str(artist["nationality"])
        )

    subtitle = " · ".join(
        subtitle_parts
    )

    if subtitle:
        print(
            c.accent(
                subtitle.center(width)
            )
        )

    print(
        c.title(
            rule(width, "═")
        )
    )

    print(
        c.dim(
            f"  {screen_name}"
        )
    )

    print()


# ============================================================================
# DESCRIPTION
# ============================================================================

def render_description_screen(
    artist,
    c,
):

    clear_screen()

    print_header(
        artist,
        c,
        "ARTIST DESCRIPTION",
    )

    width = terminal_width()

    if artist.get("intro"):
        print(
            c.italic(
                wrap_text(
                    artist["intro"],
                    width,
                )
            )
        )
        print()

    minutes = estimate_minutes(artist)

    print(
        c.dim(
            f"⏱  About {minutes} minute"
            f"{'s' if minutes != 1 else ''} read"
        )
    )

    print()

    print(
        c.heading("📖  BIOGRAPHY")
    )

    print(
        c.dim(
            rule(min(width, 20))
        )
    )

    biography = artist.get(
        "biography",
        "",
    )

    if biography:
        print(
            wrap_text(
                biography,
                width,
            )
        )
    else:
        print(
            c.dim(
                "No biography provided."
            )
        )

    print()

    print(
        c.heading("🎨  STYLE")
    )

    print(
        c.dim(
            rule(min(width, 14))
        )
    )

    style = artist.get(
        "style",
        "",
    )

    if style:
        print(
            wrap_text(
                style,
                width,
            )
        )
    else:
        print(
            c.dim(
                "No style information provided."
            )
        )

    print()

    print(
        c.heading("🛠  TECHNICAL SKILLSET")
    )

    print(
        c.dim(
            rule(min(width, 27))
        )
    )

    skills = artist.get(
        "technical_skillset",
        [],
    )

    if skills:
        for index, skill in enumerate(
            skills,
            start=1,
        ):
            print(
                textwrap.fill(
                    str(skill),
                    width=width - 7,
                    initial_indent=f"  {index}. ",
                    subsequent_indent="     ",
                )
            )
    else:
        print(
            c.dim(
                "No technical skillset provided."
            )
        )

    print()

    print(
        c.title(
            rule(width)
        )
    )

    print(
        c.green(
            "  ENTER / SPACE / →   "
            "View artworks"
        )
    )

    print(
        c.dim(
            "  Q / ESC             Quit"
        )
    )

    print()


# ============================================================================
# ARTWORK LIST
# ============================================================================

def render_artwork_list_screen(
    artist,
    c,
    selected_index,
):

    clear_screen()

    works = artist.get(
        "top_works",
        [],
    )

    print_header(
        artist,
        c,
        "EXAMPLE ARTWORKS",
    )

    width = terminal_width()

    if not works:
        print(
            c.yellow(
                "No example artworks are available."
            )
        )

        print()

        print(
            c.green(
                "  ← / BACKSPACE   Back"
            )
        )

        print(
            c.dim(
                "  Q / ESC         Quit"
            )
        )

        return

    print(
        c.dim(
            "Use ↑ / ↓ to select."
        )
    )

    print(
        c.dim(
            "ENTER / SPACE / B opens the artwork."
        )
    )

    print()

    for index, work in enumerate(works):

        title = work.get(
            "title",
            "Untitled",
        )

        year = work.get(
            "year",
            "",
        )

        if year:
            title = f"{title} ({year})"

        note = work.get(
            "note",
            "",
        )

        available_marker = (
            "  🔗"
            if (
                get_artwork_image_urls(work)
                or get_artwork_link(work)
            )
            else "  —"
        )

        if index == selected_index:

            print(
                c.title(
                    f"  ❯ {index + 1}. "
                    f"{title}"
                    f"{available_marker}"
                )
            )

            if note:

                short_note = str(note)

                if len(short_note) > 180:
                    short_note = (
                        short_note[:177]
                        + "..."
                    )

                print(
                    c.accent(
                        textwrap.fill(
                            short_note,
                            width=width - 8,
                            initial_indent="      ",
                            subsequent_indent="      ",
                        )
                    )
                )

            print()

        else:

            print(
                f"    {index + 1}. "
                f"{title}"
                f"{available_marker}"
            )

    selected = works[selected_index]

    print(
        c.title(
            rule(width)
        )
    )

    selected_title = selected.get(
        "title",
        "Untitled",
    )

    selected_year = selected.get(
        "year",
        "",
    )

    if selected_year:
        selected_title = (
            f"{selected_title} "
            f"({selected_year})"
        )

    print(
        c.heading(
            f"Selected: {selected_title}"
        )
    )

    images = get_artwork_image_urls(
        selected
    )

    link = get_artwork_link(
        selected
    )

    if images:
        print(
            c.green(
                f"  🖼 {len(images)} image"
                f"{'s' if len(images) != 1 else ''} available"
            )
        )

    elif link:
        print(
            c.green(
                "  🔗 Artwork page available"
            )
        )

    else:
        print(
            c.yellow(
                "  No image/link available"
            )
        )

    print()

    print(
        c.title(
            rule(width)
        )
    )

    print(
        c.green(
            "  ↑ / ↓              Select artwork"
        )
    )

    print(
        c.green(
            "  ENTER / SPACE / B  Open artwork"
        )
    )

    print(
        c.dim(
            "  ← / BACKSPACE      Back"
        )
    )

    print(
        c.dim(
            "  Q / ESC            Quit"
        )
    )

    print()


# ============================================================================
# INTERACTIVE VIEWER
# ============================================================================

def interactive_viewer(
    artist,
    c,
):

    works = artist.get(
        "top_works",
        [],
    )

    mode = 0
    selected_index = 0

    hide_cursor()

    try:

        while True:

            if mode == 0:

                render_description_screen(
                    artist,
                    c,
                )

            else:

                if works:
                    selected_index = max(
                        0,
                        min(
                            selected_index,
                            len(works) - 1,
                        ),
                    )
                else:
                    selected_index = 0

                render_artwork_list_screen(
                    artist,
                    c,
                    selected_index,
                )

            key = read_key()

            # ---------------------------------------------------------------
            # QUIT / SKIP
            #
            # On the description screen, SPACE is deliberately accepted
            # as a quick "skip/finish" command when the user is not trying
            # to enter the artwork list.
            #
            # ENTER still opens artworks because that is the main navigation.
            # Q / ESC always exits immediately.
            # ---------------------------------------------------------------

            if key in ("q", "ESC"):
                clear_screen()

                print(
                    c.title(
                        f"✓ Finished with "
                        f"{artist.get('name', 'artist')}"
                    )
                )

                print()

                return

            # ---------------------------------------------------------------
            # DESCRIPTION
            # ---------------------------------------------------------------

            if mode == 0:

                if key in (
                    "ENTER",
                    "SPACE",
                    "RIGHT",
                    "DOWN",
                ):
                    mode = 1
                    selected_index = 0
                    continue

            # ---------------------------------------------------------------
            # ARTWORK LIST
            # ---------------------------------------------------------------

            if mode == 1:

                if not works:

                    if key in (
                        "LEFT",
                        "BACKSPACE",
                    ):
                        mode = 0

                    continue

                if key == "DOWN":

                    if selected_index < len(works) - 1:
                        selected_index += 1
                    else:
                        selected_index = 0

                    continue

                if key == "UP":

                    if selected_index > 0:
                        selected_index -= 1
                    else:
                        selected_index = len(works) - 1

                    continue

                if key == "RIGHT":

                    if selected_index < len(works) - 1:
                        selected_index += 1
                    else:
                        selected_index = 0

                    continue

                if key in (
                    "LEFT",
                    "BACKSPACE",
                ):

                    mode = 0
                    continue

                if key in (
                    "ENTER",
                    "SPACE",
                    "b",
                ):

                    selected_work = works[
                        selected_index
                    ]

                    url = get_artwork_url(
                        selected_work
                    )

                    if not url:
                        continue

                    open_url(url)

                    continue

    finally:

        show_cursor()


# ============================================================================
# LIST
# ============================================================================

def cmd_list(
    artists,
    c,
):

    print()

    print(
        c.heading(
            f"Artist database "
            f"({len(artists)} total)"
        )
    )

    print()

    by_discipline = {}

    for artist in artists:

        discipline = artist.get(
            "discipline",
            "Other",
        )

        by_discipline.setdefault(
            discipline,
            [],
        ).append(artist)

    for discipline in sorted(
        by_discipline
    ):

        print(
            c.bold(discipline)
        )

        for artist in sorted(
            by_discipline[discipline],
            key=lambda x: x["name"],
        ):

            print(
                f"  • {artist['name']} "
                f"({artist.get('years', '')})"
            )

        print()


# ============================================================================
# STATS
# ============================================================================

def cmd_stats(
    artists,
    state,
    pool_key,
    c,
):

    names = {
        artist["name"]
        for artist in artists
    }

    pool = (
        state
        .get("pools", {})
        .get(pool_key, {})
    )

    history = pool.get(
        "history",
        [],
    )

    seen_names = {
        item["name"]
        for item in history
    }

    seen_in_db = (
        seen_names & names
    )

    print()

    print(
        c.heading(
            f"Your progress "
            f"({pool_key})"
        )
    )

    print()

    print(
        f"  Artists in this pool     : "
        f"{len(names)}"
    )

    print(
        f"  Distinct artists seen   : "
        f"{len(seen_in_db)}"
    )

    print(
        f"  Remaining in this cycle : "
        f"{len(pool.get('queue', []))}"
    )

    if history:

        last = history[-1]

        print(
            f"  Last shown              : "
            f"{last['name']} "
            f"on {last['date']}"
        )

    print()


# ============================================================================
# FIND
# ============================================================================

def find_by_name(
    artists,
    query,
):

    query_lower = query.strip().lower()

    exact = [
        artist
        for artist in artists
        if artist["name"].lower() == query_lower
    ]

    if exact:
        return exact[0]

    partial = [
        artist
        for artist in artists
        if query_lower in artist["name"].lower()
    ]

    if len(partial) == 1:
        return partial[0]

    if len(partial) > 1:

        print(
            f"Multiple matches for '{query}':"
        )

        for artist in partial:
            print(
                f"  - {artist['name']}"
            )

        return None

    print(
        f"No artist found matching '{query}'."
    )

    return None


# ============================================================================
# QUIZ
# ============================================================================

NAME_STOPWORDS = {
    "van", "von", "de", "da", "di", "der", "den", "la", "le", "el",
}


def redact_name(text, name):
    """
    Blank out every occurrence of the artist's name — and each
    significant part of it — in `text`, so the quiz doesn't give
    itself away in the biography or style paragraphs.
    """

    if not text:
        return text

    # Every part gets masked, including short connectors like "van" or
    # "de" — leaving them visible (e.g. "Van █████") would still give
    # the answer away. name_matches() is stricter about what counts as
    # a valid guess, but redaction itself must not leak anything.
    parts = [name] + [
        part
        for part in re.split(r"[\s.'-]+", name)
        if len(part) > 1
    ]

    # Longest first, so "Vincent van Gogh" is masked before "Gogh" alone.
    redacted = text

    for part in sorted(set(parts), key=len, reverse=True):
        redacted = re.sub(
            re.escape(part),
            "█████",
            redacted,
            flags=re.IGNORECASE,
        )

    return redacted


def name_matches(guess, artist_name):
    """
    Accept the full name, a recognizable chunk of it (e.g. "van gogh"),
    or any single significant word (e.g. "gogh", "picasso").
    """

    guess = guess.strip().lower()

    if not guess:
        return False

    name_lower = artist_name.lower()

    if guess == name_lower:
        return True

    if len(guess) >= 3 and guess in name_lower:
        return True

    tokens = [
        token
        for token in re.split(r"[\s-]+", name_lower)
        if token not in NAME_STOPWORDS
    ]

    return guess in tokens


def render_quiz_screen(artist, c):

    clear_screen()

    width = terminal_width()

    print(c.title(rule(width, "═")))
    print(c.title("mystery artist".center(width)))

    subtitle_parts = []

    if artist.get("discipline"):
        subtitle_parts.append(str(artist["discipline"]))

    if artist.get("nationality"):
        subtitle_parts.append(str(artist["nationality"]))

    if artist.get("years"):
        subtitle_parts.append(str(artist["years"]))

    subtitle = " · ".join(subtitle_parts)

    if subtitle:
        print(c.accent(subtitle.center(width)))

    print(c.title(rule(width, "═")))
    print(c.dim("  GUESS THE ARTIST"))
    print()

    name = artist.get("name", "")

    if artist.get("intro"):
        print(
            c.italic(
                wrap_text(redact_name(artist["intro"], name), width)
            )
        )
        print()

    print(c.heading("🎨  STYLE"))
    print(c.dim(rule(min(width, 14))))

    style = artist.get("style", "")

    if style:
        print(wrap_text(redact_name(style, name), width))
    else:
        print(c.dim("No style information provided."))

    print()

    print(c.heading("📖  BIOGRAPHY"))
    print(c.dim(rule(min(width, 20))))

    biography = artist.get("biography", "")

    if biography:
        print(wrap_text(redact_name(biography, name), width))
    else:
        print(c.dim("No biography provided."))

    print()

    print(c.title(rule(width)))

    print(
        c.dim(
            "  Type a guess and press ENTER "
            "(blank = reveal, Q = quit the quiz)."
        )
    )

    print()


def run_quiz(artists, c):
    """
    Guess-the-artist quiz: show intro/style/biography with the name
    redacted, and ask the user to identify who it is. On reveal, offers
    to drop straight into the normal artist/artwork viewer.
    """

    artist = random.choice(artists)

    render_quiz_screen(artist, c)

    try:
        guess = input("> ").strip()
    except EOFError:
        guess = ""

    print()

    if guess.lower() == "q":
        print(c.dim("Quiz cancelled."))
        print()
        return

    name = artist.get("name", "Unknown artist")

    if guess and name_matches(guess, name):
        print(c.green(f"✓ Correct! It was {name}."))
    elif guess:
        print(c.yellow(f"✗ Not quite. It was {name}."))
    else:
        print(c.heading(f"It was {name}."))

    print()

    try:
        reveal = input(
            c.dim("See the full profile and artworks? [Y/n] ")
        ).strip().lower()
    except EOFError:
        reveal = "n"

    if reveal in ("", "y", "yes"):
        interactive_viewer(artist, c)


# ============================================================================
# MAIN
# ============================================================================

CONTROLS_EPILOG = """\
controls
  description screen
    ENTER / SPACE / RIGHT / DOWN   open artwork list
    Q / ESC                        quit
  artwork screen
    UP / DOWN                      select artwork
    ENTER / SPACE / B              open selected artwork
    LEFT / BACKSPACE               back to description
    Q / ESC                        quit

examples
  python3 daily_art.py                          today's pick, art + photography
  python3 daily_art.py --category photography    today's pick, photographers only
  python3 daily_art.py --random                  a random artist right now
  python3 daily_art.py --quiz                    guess the artist from style alone
  python3 daily_art.py --name "Klimt"             jump to a specific artist
  python3 daily_art.py --list                    list every artist in the pool
  python3 daily_art.py --stats                   see your progress
"""


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Interactive daily introduction "
            "to a great artist or photographer."
        ),
        epilog=CONTROLS_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--category",
        choices=[
            "art",
            "photography",
            "both",
        ],
        default="both",
        help="which artist pool to draw from (default: both)",
    )

    parser.add_argument(
        "--random",
        action="store_true",
        help="show a random artist right now, without touching the daily cycle",
    )

    parser.add_argument(
        "--quiz",
        action="store_true",
        help="guess the artist from a redacted style/biography, then reveal",
    )

    parser.add_argument(
        "--name",
        type=str,
        help="jump straight to a specific artist (partial match)",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="list every artist in the selected pool, grouped by discipline",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="show how many artists you've seen and how many remain",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="wipe your history (all pools) and start a fresh shuffled cycle",
    )

    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="load a single custom artist database (overrides --category)",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="plain text output, no ANSI colors or hyperlinks",
    )

    args = parser.parse_args()

    c = Palette(
        enabled=(
            supports_color()
            and not args.no_color
        )
    )

    artists = load_artists(
        args.category,
        explicit_data=args.data,
    )

    if not artists:

        print()
        print(
            "No artists available."
        )
        print()

        return 1

    pool_key = (
        "custom:" + args.data
        if args.data
        else args.category
    )

    if args.list:

        cmd_list(
            artists,
            c,
        )

        return 0

    if args.quiz:

        run_quiz(
            artists,
            c,
        )

        return 0

    if args.reset:

        if STATE_PATH.exists():

            try:
                STATE_PATH.unlink()
            except OSError as exc:
                print(
                    f"Could not reset state: {exc}"
                )
                return 1

        print()
        print(
            c.green(
                "✓ History reset."
            )
        )
        print()

        return 0

    state = load_state()

    if args.stats:

        cmd_stats(
            artists,
            state,
            pool_key,
            c,
        )

        return 0

    if args.name:

        artist = find_by_name(
            artists,
            args.name,
        )

        if artist is None:
            return 1

        interactive_viewer(
            artist,
            c,
        )

        return 0

    if args.random:

        artist = random.choice(artists)

        interactive_viewer(
            artist,
            c,
        )

        return 0

    artist = get_today_artist(
        artists,
        state,
        pool_key,
    )

    save_state(state)

    interactive_viewer(
        artist,
        c,
    )

    return 0


# ============================================================================
# ENTRY
# ============================================================================

if __name__ == "__main__":

    try:
        sys.exit(main())

    except KeyboardInterrupt:

        show_cursor()
        clear_screen()

        print(
            "\n✓ Exited.\n"
        )

        sys.exit(0)

    except Exception as exc:

        show_cursor()

        print()
        print(
            "An unexpected error occurred:"
        )
        print()
        print(
            f"  {type(exc).__name__}: {exc}"
        )
        print()

        sys.exit(1)

    finally:

        show_cursor()

