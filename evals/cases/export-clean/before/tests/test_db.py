from app.db import connect


def test_schema_loads():
    conn = connect()
    assert conn.execute("SELECT count(*) FROM orders").fetchone() == (0,)
