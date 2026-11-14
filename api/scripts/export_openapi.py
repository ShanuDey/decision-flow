"""Write the FastAPI OpenAPI schema to openapi.json (input for the web client generator)."""

import json
import os
from pathlib import Path

# The schema does not depend on auth, but app creation needs a provider to start.
os.environ.setdefault(
    "AUTH_PROVIDERS",
    '[{"type":"jwt","name":"schema","issuer":"https://schema.invalid",'
    '"audience":"schema","jwks_url":"https://schema.invalid/jwks"}]',
)

from app.main import app  # noqa: E402

OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"

if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
