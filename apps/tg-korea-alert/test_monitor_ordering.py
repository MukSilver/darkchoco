import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from company_country_classifier import Classification
from korea_alert_monitor import AlertMonitor, open_database


class FakeClassifier:
    async def classify(self, text):
        return Classification(False, True, "test", 1.0)


class FakeClient:
    def __init__(self, messages):
        self.messages = messages

    async def iter_messages(self, entity, min_id, reverse):
        messages = [message for message in self.messages if message.id > min_id]
        for message in sorted(messages, key=lambda item: item.id, reverse=not reverse):
            yield message


class MonitorOrderingTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = open_database(Path(self.temp_dir.name) / "monitor.db")
        self.entity = SimpleNamespace(id=123, title="Test channel", username="test")
        self.monitor = AlertMonitor.__new__(AlertMonitor)
        self.monitor.database = self.database
        self.monitor.classifier = FakeClassifier()
        self.monitor.webhook_url = "unused"

    async def asyncTearDown(self):
        self.database.close()
        self.temp_dir.cleanup()

    async def test_late_lower_id_is_not_dropped(self):
        high = SimpleNamespace(id=103, raw_text="high")
        late = SimpleNamespace(id=101, raw_text="late")

        await self.monitor.process_message(self.entity, high)
        await self.monitor.process_message(self.entity, late)
        await self.monitor.process_message(self.entity, late)

        rows = self.database.execute(
            "SELECT message_id FROM processed_messages ORDER BY message_id"
        ).fetchall()
        self.assertEqual(rows, [(101,), (103,)])
        self.assertEqual(self.monitor.last_message_id(self.entity.id), 103)

    async def test_catch_up_processes_burst_in_id_order(self):
        messages = [
            SimpleNamespace(id=103, raw_text="third"),
            SimpleNamespace(id=101, raw_text="first"),
            SimpleNamespace(id=102, raw_text="second"),
        ]
        self.monitor.client = FakeClient(messages)

        await self.monitor.catch_up(self.entity)

        rows = self.database.execute(
            "SELECT message_id FROM processed_messages ORDER BY processed_at, message_id"
        ).fetchall()
        self.assertEqual(rows, [(101,), (102,), (103,)])


if __name__ == "__main__":
    unittest.main()
