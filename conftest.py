import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _empty_cache():
    """Every test starts with an empty cache: standings, the navigation's live contests and the
    rate-limit counters are cached by primary key, and primary keys repeat between tests."""
    cache.clear()
