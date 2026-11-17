import os


def connect():
    import psycopg  # imported lazily so unit tests don't need the driver

    return psycopg.connect(os.environ["DATABASE_URL"])
