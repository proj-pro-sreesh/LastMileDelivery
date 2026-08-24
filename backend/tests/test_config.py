"""GAP 4: hosted-Postgres URL normalization (Render hands out postgres:// URLs)."""

from app.core.config import Settings


def test_postgres_scheme_normalized_with_ssl():
    settings = Settings(database_url="postgres://user:pass@dbhost:5432/lastmile_delivery", _env_file=None)
    assert settings.database_url == (
        "postgresql+psycopg://user:pass@dbhost:5432/lastmile_delivery?sslmode=require"
    )


def test_postgresql_scheme_also_normalized():
    settings = Settings(database_url="postgresql://user:pass@dbhost:5432/lastmile_delivery", _env_file=None)
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.database_url.endswith("sslmode=require")


def test_existing_sslmode_not_duplicated_and_local_urls_untouched():
    kept = Settings(database_url="postgres://u:p@h/db?sslmode=disable", _env_file=None)
    assert "sslmode=disable" in kept.database_url and kept.database_url.count("sslmode") == 1

    local = Settings(_env_file=None)
    assert local.database_url == "postgresql+psycopg:///lastmile_delivery"
