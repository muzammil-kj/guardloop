from unittest.mock import MagicMock

import pytest


class FakeQuery:
    """Chainable stand-in for a Supabase query. Filters are accepted but not
    applied: each test configures exactly the rows its scenario needs."""

    def __init__(self, data=None, count=None):
        self._data = data if data is not None else []
        self._count = count
        self.inserted = None
        self.upserted = None
        self.upsert_kwargs = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def delete(self):
        return self

    def insert(self, row):
        self.inserted = row
        self._data = [{"id": 1, "created_at": "2026-01-01T00:00:00+00:00", **row}]
        return self

    def upsert(self, row, **kwargs):
        self.upserted = row
        self.upsert_kwargs = kwargs
        return self

    def execute(self):
        result = MagicMock()
        result.data = self._data
        result.count = self._count
        return result


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return self.tables[name]


@pytest.fixture
def make_fake_supabase():
    def _make(**tables):
        return FakeSupabase(tables)

    return _make


@pytest.fixture
def fake_query():
    return FakeQuery
