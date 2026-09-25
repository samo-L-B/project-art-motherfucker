# Daily Art & Photography — 5-Minute Terminal Briefing

A small, dependency-free Python script that gives you a quick daily intro to a
great artist or photographer, right in your terminal: **intro → biography →
style → technical skillset → top works**, in about 5 minutes of reading.

No installs, no API keys, no internet connection required — everything runs
from a local JSON file.

---

## Requirements

- Python 3.7+ (uses only the standard library: `argparse`, `json`, `random`,
  `textwrap`, `pathlib`, etc.)
- A terminal. Colors work out of the box on macOS/Linux; on Windows they're
  enabled automatically on modern terminals (Windows Terminal, PowerShell 7+).

## Setup

1. Put `daily_art.py`, `art_data.json`, and `photography_data.json` in the
   **same folder**.
2. Run it:

   ```bash
   python3 daily_art.py
   ```

By default it draws from **both** files combined. Use `--category art` or
`--category photography` to pull from just one.

That's it. State (what you've seen, and today's pick) is stored separately in
`~/.daily_art/state.json`, so it won't clutter the script's folder and will
persist even if you move the script. Each category keeps its own independent
progress — switching between `--category art`, `--category photography`, and
the combined default won't disturb each other's cycles.

### Optional: make it a one-word command

**macOS/Linux** — add an alias to your shell config (`~/.bashrc`, `~/.zshrc`):
```bash
alias art="python3 /full/path/to/daily_art.py"
```
Then just run `art` each morning.

**Windows** — create a `.bat` file somewhere on your PATH:
```bat
@echo off
python "C:\full\path\to\daily_art.py" %*
```

---

## Usage

| Command | What it does |
|---|---|
| `python3 daily_art.py` | Show **today's** artist from art + photography combined (same pick all day, advances tomorrow) |
| `python3 daily_art.py --category art` | Today's artist from painters/printmakers only |
| `python3 daily_art.py --category photography` | Today's artist from photographers only |
| `python3 daily_art.py --random` | Show a random artist right now, without affecting the daily cycle |
| `python3 daily_art.py --quiz` | Guess-the-artist: intro/style/biography with the name redacted, then reveal |
| `python3 daily_art.py --name "Klimt"` | Jump straight to a specific artist (partial, case-insensitive match) |
| `python3 daily_art.py --list` | List every artist in the selected database(s), grouped by discipline |
| `python3 daily_art.py --stats` | See how many you've seen and how many remain in this cycle |
| `python3 daily_art.py --reset` | Wipe your history (all pools) and start a fresh shuffled cycle |
| `python3 daily_art.py --data other_file.json` | Load a single custom artist database (overrides `--category`) |
| `python3 daily_art.py --no-color` | Plain text output, no ANSI colors or hyperlinks (useful when piping to a file) |

Combine flags as needed, e.g. `python3 daily_art.py --category photography --list`.

Run `python3 daily_art.py --help` any time for the full option list.

---

## How the daily rotation works

- On first run, the script shuffles the full artist list into a random
  **queue** and pops the first name off it.
- That choice is stamped with today's date. Running the script again the
  *same* day always returns the same artist — it's a daily briefing, not a
  slot machine.
- The next calendar day, it pops the next name off the queue.
- Once the queue is empty (you've seen everyone), it reshuffles and starts a
  new cycle — so you never get an immediate repeat, but the order isn't
  predictable round to round.
- `--random` bypasses all of this for a quick "surprise me" look without
  disturbing your streak.

All of this state lives in `~/.daily_art/state.json`. Delete that file (or
run `--reset`) any time to start over.

---

## The two databases

**`photography_data.json`** — 10 photographers: Ansel Adams, Henri
Cartier-Bresson, Diane Arbus, Vivian Maier, Dorothea Lange, Sebastião
Salgado, Irving Penn, Annie Leibovitz, Gordon Parks, Man Ray

**`art_data.json`** — 9 painters/printmakers: Vincent van Gogh, Frida Kahlo,
Rembrandt van Rijn, Johannes Vermeer, Katsushika Hokusai, Georgia O'Keeffe,
Pablo Picasso, Caravaggio, Gustav Klimt

Each artist now includes **6 top works**, and every work has a clickable
`link` so you can actually go look at the piece — most point straight to its
Wikipedia article; a few (mainly lesser-documented individual photographs)
point to a Wikimedia Commons image search or, for Vivian Maier, her official
estate galleries at vivianmaier.com, since most of her photos were never
individually titled or catalogued.

In the terminal, links render as real clickable hyperlinks (via the OSC 8
escape sequence) in modern terminals — iTerm2, Windows Terminal, GNOME
Terminal, kitty, the VS Code integrated terminal, and others. The raw URL is
also always printed underneath, so you can copy-paste it anywhere, and
`--no-color` disables the hyperlink escape codes entirely if your terminal
doesn't support them or you're piping to a file.

### Adding your own artists

Open either JSON file and add a new object to its `"artists"` array,
following this shape:

```json
{
  "name": "Artist Name",
  "discipline": "Photography",
  "years": "1900–1980",
  "nationality": "American",
  "intro": "One punchy sentence hooking the reader.",
  "biography": "A paragraph on their life and career.",
  "style": "A paragraph on their visual/artistic approach.",
  "technical_skillset": [
    "A specific technique or method, one per line",
    "Another one"
  ],
  "top_works": [
    {
      "title": "Title of the piece",
      "year": "1950",
      "note": "A short line on why it matters.",
      "link": "https://en.wikipedia.org/wiki/..."
    }
  ]
}
```

No code changes are needed — the script picks up new entries automatically.
If you don't have a confident direct link for a work, a safe universal
fallback is a Wikimedia Commons search URL:

```
https://commons.wikimedia.org/w/index.php?search=YOUR+SEARCH+TERMS&title=Special:MediaSearch&type=image
```

Note: if you edit either artist list, the script detects the change and
reshuffles that pool's queue on the next run (so new names get included).

You can also point the script at a completely separate file with
`--data /path/to/my_artists.json` if you want a third independent
collection (e.g. sculpture, architecture, film).

---

## Files

```
daily_art.py             # the script — all logic, no external dependencies
art_data.json            # painters / printmakers / sculptors (edit or extend freely)
photography_data.json    # photographers (edit or extend freely)
README.md                # this file
```

State file (created automatically, not shipped): `~/.daily_art/state.json`

---

## Guess-the-artist quiz

`--quiz` picks a random artist from the selected pool (respects `--category`
and `--data`, and never touches your daily-pick history) and shows the
intro, style, and biography with every occurrence of the artist's name —
first name, surname, and connectors like "van" or "de" — blanked out as
`█████`. Type a guess and press ENTER: a full name, a surname alone
("gogh"), or a recognizable chunk ("van gogh") all count as correct. Leave
it blank to reveal, or type `q` to bail out. After the reveal you're offered
the normal artist/artwork viewer, so a quiz round can flow straight into
reading the full profile.

Because the quiz reads a plain typed line instead of raw keypresses, it also
works over SSH sessions or terminals where the arrow-key viewer's raw input
mode misbehaves.

## Ideas for extending it further

- A `cron` / Task Scheduler entry to email or notify yourself the daily pick
  automatically each morning.
- A companion `--images` flag that opens a web search for the top works
  listed, since this script itself is offline/text-only by design.
