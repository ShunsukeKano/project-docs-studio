"""Write backend/openapi.json from the app. It needs no database connection."""

import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app

OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> None:
    # A fixed local configuration, so the output never depends on the caller's environment.
    app = create_app(Settings(env="local", database_url=None, basic_auth_enabled=False))
    OUTPUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
