import csv
import io

import pytest

from app.auth import User
from app.db import connect
from app.exports import DEFAULT_COLUMNS, export_orders_csv, load_presets

ADMIN = User(1, "boss@shop.test", is_admin=True)


@pytest.fixture
def db():
    conn = connect()
    conn.executemany("INSERT INTO customers (id, email, name) VALUES (?, ?, ?)",
                     [(1, "ann@x.test", "Ann"), (2, "eve@x.test", "=HYPERLINK(\"http://evil\")")])
    conn.executemany("INSERT INTO orders (id, customer_id, total_cents, status, created_at) VALUES (?, ?, ?, ?, ?)",
                     [(10, 1, 2500, "paid", "2026-01-02T10:00:00Z"), (11, 2, -500, "refunded", "2026-01-03T10:00:00Z")])
    return conn


def rows(resp):
    return list(csv.reader(io.StringIO(resp.body.decode())))


def test_admin_only(db):
    assert export_orders_csv(db, User(2, "u@x.test")).status == 403


def test_default_columns(db):
    resp = export_orders_csv(db, ADMIN)
    assert resp.status == 200
    assert rows(resp)[0] == DEFAULT_COLUMNS
    assert rows(resp)[1] == ["10", "ann@x.test", "2500", "2026-01-02T10:00:00Z"]


def test_unknown_column_is_400(db):
    resp = export_orders_csv(db, ADMIN, columns="id,password_hash")
    assert resp.status == 400
    assert b"password_hash" in resp.body


def test_sql_in_column_list_is_rejected(db):
    assert export_orders_csv(db, ADMIN, columns="id FROM customers;--").status == 400


def test_formulas_are_neutralized_but_numbers_are_not(db):
    out = rows(export_orders_csv(db, ADMIN, columns="id,customer_name,total_cents"))
    assert out[2] == ["11", "'=HYPERLINK(\"http://evil\")", "-500"]


def test_presets(db):
    presets = load_presets()
    assert presets["finance"] == ["id", "total_cents", "status", "created_at"]
    assert rows(export_orders_csv(db, ADMIN, preset="finance"))[0] == presets["finance"]
    assert export_orders_csv(db, ADMIN, preset="nope").status == 400


def test_etag_304(db):
    first = export_orders_csv(db, ADMIN)
    again = export_orders_csv(db, ADMIN, if_none_match=first.headers["ETag"])
    assert again.status == 304 and again.body == b""
