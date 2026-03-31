from __future__ import annotations

from temperance.config import load_config
from temperance.db import init_db, run_migrations


if __name__ == "__main__":
    cfg = load_config()
    init_db(cfg.db_path)
    run_migrations(cfg.db_path)
    print(f"Migrations complete for {cfg.db_path}")
