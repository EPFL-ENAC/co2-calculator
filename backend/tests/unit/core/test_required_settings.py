"""DB_URL and FRONTEND_URL have no default (#3244).

A deployment that leaves one out must not boot. An empty value counts as
left out: a Helm value rendered as "" gives ``FRONTEND_URL=``, and the app
would boot with an empty OAuth redirect and allowed origin.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("name", ["DB_URL", "FRONTEND_URL"])
def test_empty_required_setting_stops_the_boot(monkeypatch, name):
    monkeypatch.setenv(name, "")
    with pytest.raises(ValidationError, match=name):
        Settings(_env_file=None)


@pytest.mark.parametrize("name", ["DB_URL", "FRONTEND_URL"])
def test_missing_required_setting_stops_the_boot(monkeypatch, name):
    monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError, match=name):
        Settings(_env_file=None)
