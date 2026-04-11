from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

if __package__ in {None, ""}:
    SRC_ROOT = Path(__file__).resolve().parents[1]
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))
    from src.arkana_mdd_db.config import get_api_server_config
else:
    from src.arkana_mdd_db.config import get_api_server_config


def main() -> None:
    config = get_api_server_config()
    uvicorn.run("src.arkana_api_service.app:app", host=config.host, port=config.port, reload=False)


if __name__ == "__main__":
    main()
