"""Account signup."""
from __future__ import annotations

import sqlite3

from accounts import models
from core import db
from emails import templates
from emails.sender import send_email


class SignupError(Exception):
    pass


def signup(email: str, name: str, password: str, *, marketing_opt_in: bool = False,
           locale: str = "en") -> models.User:
    if len(password) < 10:
        raise SignupError("password too short")
    try:
        with db.atomic():
            user = models.create_user(email, name, password)
            models.create_profile(user.id, marketing_opt_in, locale)
            subject, body = templates.welcome(user.name, locale)
            send_email(user.email, subject, body)
    except sqlite3.IntegrityError:
        raise SignupError("email already registered")
    return user
