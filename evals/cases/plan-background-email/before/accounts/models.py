from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from core import db


@dataclass(frozen=True)
class User:
    id: int
    email: str
    name: str


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    return salt.hex() + ":" + hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()


def create_user(email: str, name: str, password: str) -> User:
    cur = db.execute("INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                     (email.lower(), name, hash_password(password)))
    return User(cur.lastrowid, email.lower(), name)


def create_profile(user_id: int, marketing_opt_in: bool, locale: str) -> None:
    db.execute("INSERT INTO profiles (user_id, marketing_opt_in, locale) VALUES (?, ?, ?)",
               (user_id, int(marketing_opt_in), locale))


def get_user(user_id: int) -> User | None:
    row = db.execute("SELECT id, email, name FROM users WHERE id = ?", (user_id,)).fetchone()
    return User(row["id"], row["email"], row["name"]) if row else None


def get_locale(user_id: int) -> str:
    row = db.execute("SELECT locale FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    return row["locale"] if row else "en"
