WELCOME_SUBJECT = {"en": "Welcome to Shopfront", "fr": "Bienvenue sur Shopfront"}
WELCOME_BODY = {
    "en": "Hi {name},\n\nThanks for signing up. Your account is ready.\n",
    "fr": "Bonjour {name},\n\nMerci de votre inscription. Votre compte est prêt.\n",
}


def welcome(name: str, locale: str = "en") -> tuple[str, str]:
    loc = locale if locale in WELCOME_SUBJECT else "en"
    return WELCOME_SUBJECT[loc], WELCOME_BODY[loc].format(name=name)
