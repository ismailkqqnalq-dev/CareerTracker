from app.database.session import create_database_engine


def test_sqlite_engine_enables_foreign_key_cascades():
    engine = create_database_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()
