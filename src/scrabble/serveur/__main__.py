"""Permet ``python -m scrabble.serveur`` (issue #475)."""

from __future__ import annotations

from scrabble.serveur.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
