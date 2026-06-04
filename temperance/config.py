from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    db_path: Path
    import_dir: Path
    private_export_dir: Path
    garmin_email: str | None
    garmin_password: str | None


def load_config() -> AppConfig:
    """Load configuration from environment and local env files."""
    root = Path(__file__).resolve().parent
    load_dotenv(
        Path.home() / ".config" / "temperance" / "temperance.env",
        override=False,
    )
    load_dotenv(root / ".env", override=False)
    load_dotenv(override=False)

    private_dir = root / "data" / "private"

    return AppConfig(
        db_path=private_dir / "temperance.db",
        import_dir=root / "data" / "imports",
        private_export_dir=private_dir / "exports",
        garmin_email=os.getenv("GARMIN_EMAIL"),
        garmin_password=os.getenv("GARMIN_PASSWORD"),
    )
