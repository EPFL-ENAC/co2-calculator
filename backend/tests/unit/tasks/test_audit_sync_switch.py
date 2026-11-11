"""The Elasticsearch audit export is off by default (#500).

Off, an audit write schedules no sync task: the record stays pending in the
database, and enabling the export later sends it.
"""

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.tasks.audit_sync_tasks import sync_audit_records_with_elasticsearch


async def test_disabled_export_schedules_nothing(monkeypatch):
    monkeypatch.setattr(get_settings(), "ELASTICSEARCH_ENABLED", False)
    tasks = BackgroundTasks()

    result = await sync_audit_records_with_elasticsearch(tasks)

    assert result == {"status": "elasticsearch disabled"}
    assert tasks.tasks == []


async def test_enabled_export_schedules_sync_and_retry(monkeypatch):
    monkeypatch.setattr(get_settings(), "ELASTICSEARCH_ENABLED", True)
    tasks = BackgroundTasks()

    await sync_audit_records_with_elasticsearch(tasks)

    assert len(tasks.tasks) == 2
