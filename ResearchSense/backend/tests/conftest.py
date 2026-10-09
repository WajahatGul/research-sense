"""Every test gets its own accounts database.

The accounts database holds real claims, corrections and the activity log;
a test that searched for nonsense, logged in or refreshed used to write
rows into the developer's copy. Tests that need particular contents set
DB_PATH themselves, which overrides this.
"""

import pytest


@pytest.fixture(autouse=True)
def _own_accounts_db(tmp_path, monkeypatch):
    import app.repositories.accounts as accounts_mod
    from app.core.deps import get_auth_service
    from app.repositories.accounts import AccountStore

    monkeypatch.setattr(accounts_mod, "DB_PATH", tmp_path / "accounts.db")
    monkeypatch.setenv("RS_BACKUP_DIR", str(tmp_path / "backups"))
    AccountStore._instance = None
    get_auth_service.cache_clear()
    yield
    AccountStore._instance = None
    get_auth_service.cache_clear()
