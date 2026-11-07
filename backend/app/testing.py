from sqlalchemy.engine import make_url


def validate_test_database(test_url: str, development_url: str | None) -> None:
    target = make_url(test_url)
    if target.get_backend_name() != "postgresql" or not (target.database or "").endswith("_test"):
        raise ValueError("Tests require a PostgreSQL database name ending in _test")
    if development_url and target.database == make_url(development_url).database:
        raise ValueError("Test and development database names must differ")
