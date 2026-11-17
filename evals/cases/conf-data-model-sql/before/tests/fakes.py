class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        self.conn.executed.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.conn.rows.pop(0) if self.conn.rows else None

    def fetchall(self):
        rows, self.conn.rows = self.conn.rows, []
        return rows


class FakeConn:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.executed = []
        self.autocommit = False

    def cursor(self):
        return FakeCursor(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
