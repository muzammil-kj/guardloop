from unittest.mock import MagicMock

import pytest


class FakeQuery:
    """Chainable stand-in for a Supabase query. Filters are accepted but not
    applied: each test configures exactly the rows its scenario needs.

    - `data`        what select/delete/upsert return
    - `update_data` what update returns (an empty list means "no row matched",
                    which is how a lost atomic claim looks)
    - `.inserted`, `.upserted`, `.updates` record what the code wrote
    """

    def __init__(self, data=None, count=None, update_data=None):
        self._data = data if data is not None else []
        self._count = count
        self._update_data = update_data if update_data is not None else [{"id": 1}]
        self._insert_data = []
        self._mode = "select"
        self.inserted = None
        self.upserted = None
        self.upsert_kwargs = None
        self.updates = []

    # --- query starters -------------------------------------------------
    def select(self, *args, **kwargs):
        self._mode = "select"
        return self

    def insert(self, row):
        self.inserted = row
        self._insert_data = [{"id": 1, "created_at": "2026-01-01T00:00:00+00:00", **row}]
        self._mode = "insert"
        return self

    def update(self, payload):
        self.updates.append(payload)
        self._mode = "update"
        return self

    def upsert(self, row, **kwargs):
        self.upserted = row
        self.upsert_kwargs = kwargs
        self._mode = "upsert"
        return self

    def delete(self):
        self._mode = "delete"
        return self

    # --- filters / modifiers (accepted, not applied) --------------------
    def eq(self, *args, **kwargs):
        return self

    def lt(self, *args, **kwargs):
        return self

    def is_(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        result = MagicMock()
        if self._mode == "update":
            result.data = self._update_data
        elif self._mode == "insert":
            result.data = self._insert_data
        else:
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
