"""Enable ``python -m scrapehub`` to invoke the Typer CLI."""

from __future__ import annotations

from scrapehub.cli import app

if __name__ == "__main__":  # pragma: no cover - thin shim
    app()
