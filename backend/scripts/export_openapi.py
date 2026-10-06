"""Write the OpenAPI schema to docs/openapi.json (source for frontend TypeScript types).

python -m scripts.export_openapi
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app

TARGET = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def main() -> None:
    schema = create_app(Settings(app_env="test")).openapi()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
