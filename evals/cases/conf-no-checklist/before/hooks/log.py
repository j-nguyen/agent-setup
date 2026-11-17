"""Project-wide structured logging. Use get_logger(__name__) everywhere."""
import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        payload.update(getattr(record, "fields", {}))
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
