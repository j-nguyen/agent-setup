ENG-103: Reminder with "1h30m" crashes

**Reported by:** QA (Lee) · **Priority:** High · **Labels:** bug, reminders · **Found in:** v1.4.0

On v1.4.0, creating a reminder with the duration "1h30m" crashes with:

    ValueError: invalid duration '1h30m'

Single units like "90m" or "2h" work fine.
