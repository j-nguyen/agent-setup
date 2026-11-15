"""Transactional outbox: events are written in the same transaction as the data
change, and a relay publishes them afterwards (at least once; consumers dedupe on event_id)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, Index, String, or_, select, text, update
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base

CLAIM_SECONDS = 60


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    # The relay only ever looks for unsent rows; sent rows are pruned by the existing prune_outbox job.
    __table_args__ = (Index("ix_outbox_events_unsent", "id", postgresql_where=text("sent_at IS NULL")),)
    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    claimed_until: Mapped[datetime | None]
    sent_at: Mapped[datetime | None]


def relay_outbox(Session, publisher, batch_size: int = 100) -> int:
    """Publish up to batch_size pending events. Safe to run in several processes at once."""
    now = datetime.now(timezone.utc)
    # 1. Claim a batch in a short transaction. SKIP LOCKED lets concurrent relays
    #    take different rows instead of waiting on each other.
    with Session.begin() as session:
        rows = session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.sent_at.is_(None),
                   or_(OutboxEvent.claimed_until.is_(None), OutboxEvent.claimed_until < now))
            .order_by(OutboxEvent.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.claimed_until = now + timedelta(seconds=CLAIM_SECONDS)
        claimed = [(r.id, r.topic, r.key, r.payload) for r in rows]

    # 2. Publish outside any transaction, so no locks or connections are held on the network.
    sent: list[int] = []
    try:
        for event_id, topic, key, payload in claimed:
            publisher.publish(topic, key, json.dumps({"event_id": event_id, **payload}))
            sent.append(event_id)
    finally:
        # 3. Mark what was published; anything left is retried once its claim expires.
        if sent:
            with Session.begin() as session:
                session.execute(update(OutboxEvent).where(OutboxEvent.id.in_(sent))
                                .values(sent_at=datetime.now(timezone.utc)))
    return len(sent)
