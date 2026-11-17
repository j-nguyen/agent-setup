import unittest

from core import db
from jobs import queue, worker
from jobs.handlers import HANDLERS, handler
from tests.base import DbTestCase

calls = []


@handler("test.flaky")
def flaky(payload):
    calls.append(payload)
    if payload.get("fail_times", 0) >= len(calls):
        raise RuntimeError("boom")


class JobsTest(DbTestCase):
    def setUp(self):
        super().setUp()
        calls.clear()

    def test_runs_and_marks_done(self):
        jid = queue.enqueue("test.flaky", {"n": 1})
        self.assertTrue(worker.run_once())
        self.assertEqual(queue.get(jid)["status"], "done")

    def test_retries_with_backoff_then_succeeds(self):
        jid = queue.enqueue("test.flaky", {"fail_times": 1})
        worker.run_once(now=1e10)
        job = queue.get(jid)
        self.assertEqual((job["status"], job["attempts"]), ("queued", 1))
        self.assertEqual(job["run_at"], 1e10 + worker.BACKOFF_BASE_SECONDS)
        self.assertFalse(worker.run_once(now=1e10 + 1))  # not due yet
        worker.run_once(now=1e10 + 31)
        self.assertEqual(queue.get(jid)["status"], "done")

    def test_dead_after_max_attempts(self):
        jid = queue.enqueue("test.flaky", {"fail_times": 99}, max_attempts=2)
        worker.run_once(now=1e10)
        worker.run_once(now=1e11)
        self.assertEqual(queue.get(jid)["status"], "dead")

    def test_dedupe_key(self):
        self.assertIsNotNone(queue.enqueue("test.flaky", {}, dedupe_key="k"))
        self.assertIsNone(queue.enqueue("test.flaky", {}, dedupe_key="k"))

    def test_enqueue_rolls_back_with_transaction(self):
        with self.assertRaises(RuntimeError):
            with db.atomic():
                queue.enqueue("test.flaky", {})
                raise RuntimeError("abort")
        self.assertIsNone(db.execute("SELECT 1 FROM jobs").fetchone())

    def test_on_commit_runs_after_commit_only(self):
        ran = []
        with db.atomic():
            db.on_commit(lambda: ran.append(1))
            self.assertEqual(ran, [])
        self.assertEqual(ran, [1])
        with self.assertRaises(RuntimeError):
            with db.atomic():
                db.on_commit(lambda: ran.append(2))
                raise RuntimeError
        self.assertEqual(ran, [1])

    def test_unknown_kind_fails(self):
        HANDLERS.pop("nope", None)
        jid = queue.enqueue("nope", {})
        worker.run_once()
        self.assertEqual(queue.get(jid)["attempts"], 1)


if __name__ == "__main__":
    unittest.main()
