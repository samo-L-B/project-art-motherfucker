"""Tests for daily_art.py. Run: python3 -m unittest discover -s tests"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SCRIPT = HERE / "daily_art.py"

spec = importlib.util.spec_from_file_location("daily_art", SCRIPT)
daily_art = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily_art)

REQUIRED = ("name", "discipline", "years", "nationality", "intro",
            "biography", "style", "technical_skillset", "top_works")


def all_artists():
    for path in daily_art.DATA_FILES.values():
        for artist in json.loads(path.read_text())["artists"]:
            yield path.name, artist


class NameMatches(unittest.TestCase):
    def test_accepts_full_name_word_runs_and_significant_words(self):
        for guess, name in [
            ("Vincent van Gogh", "Vincent van Gogh"),
            ("van gogh", "Vincent van Gogh"),
            ("gogh", "Vincent van Gogh"),
            ("  PICASSO ", "Pablo Picasso"),
            ("cartier-bresson", "Henri Cartier-Bresson"),
            ("cartier bresson", "Henri Cartier-Bresson"),
            ("bresson", "Henri Cartier-Bresson"),
            ("okeeffe", "Georgia O'Keeffe"),
            ("o'keeffe", "Georgia O'Keeffe"),
            ("sebastiao salgado", "Sebastião Salgado"),
            ("caravaggio", "Caravaggio"),
        ]:
            self.assertTrue(daily_art.name_matches(guess, name), (guess, name))

    def test_rejects_fragments_connectors_and_wrong_names(self):
        for guess, name in [
            ("", "Pablo Picasso"),
            ("van", "Vincent van Gogh"),
            ("van van", "Rembrandt van Rijn"),
            ("ent", "Vincent van Gogh"),
            ("ans", "Ansel Adams"),
            ("ann", "Johannes Vermeer"),
            ("gogh van", "Vincent van Gogh"),
            ("picass", "Pablo Picasso"),
            ("klimt", "Pablo Picasso"),
        ]:
            self.assertFalse(daily_art.name_matches(guess, name), (guess, name))

    def test_every_artist_is_guessable_by_full_name_and_by_last_word(self):
        for _, artist in all_artists():
            name = artist["name"]
            self.assertTrue(daily_art.name_matches(name, name))
            self.assertTrue(daily_art.name_matches(name.split()[-1], name), name)


class RedactName(unittest.TestCase):
    def test_quiz_text_never_leaks_any_part_of_the_name(self):
        for _, artist in all_artists():
            name = artist["name"]
            for field in ("intro", "biography", "style"):
                text = daily_art.redact_name(artist[field], name)
                for token in daily_art.name_tokens(name):
                    if len(token) > 2 and token not in daily_art.NAME_STOPWORDS:
                        self.assertNotIn(token, daily_art.name_tokens(text), (name, field))


class Data(unittest.TestCase):
    def test_every_artist_has_the_fields_the_screens_read(self):
        names = set()
        for file, artist in all_artists():
            missing = [k for k in REQUIRED if not artist.get(k)]
            self.assertFalse(missing, f"{file}: {artist.get('name')} lacks {missing}")
            self.assertIsInstance(artist["top_works"], list)
            for work in artist["top_works"]:
                self.assertTrue(work.get("title"), f"{artist['name']}: work without title")
            self.assertNotIn(artist["name"], names, "duplicate artist")
            names.add(artist["name"])


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        with tempfile.TemporaryDirectory() as home:
            r = subprocess.run([sys.executable, str(SCRIPT), "--no-color", *args],
                               capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL,
                               env=dict(os.environ, HOME=home))
            return r, Path(home)

    def test_list_shows_every_artist(self):
        r, _ = self.run_cli("--list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"Artist database ({len(list(all_artists()))} total)", r.stdout)

    def test_stats_runs_with_a_fresh_home(self):
        r, _ = self.run_cli("--stats")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Artists in this pool", r.stdout)


if __name__ == "__main__":
    unittest.main()
