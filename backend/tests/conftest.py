import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    """Entorno aislado: data dir temporal + BD nueva + proveedores fake."""
    monkeypatch.setenv("LYP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("TTS_PROVIDER", "fake")
    # settings es un singleton creado en import: recargar módulos de app.
    for mod in [m for m in list(sys.modules) if m.startswith("app")]:
        del sys.modules[mod]
    import app.config  # noqa: F401  (recrea settings con el nuevo entorno)
    from app import db
    from app.config import settings
    db.init(settings.db_path)
    yield settings


FIXTURES = Path(__file__).parent / "fixtures"
