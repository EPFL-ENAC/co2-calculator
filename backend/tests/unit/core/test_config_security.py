"""Regression tests: the security-critical flags default to False in code.

``TEST_LOGIN_ROUTE_ENABLED`` registers the ``/login-test`` auth bypass
(`app/api/v1/auth.py`) and ``DEBUG_STACK_TRACE_ENABLED`` returns stack traces
in responses. One image ships to dev/stage/prod with these set per
environment in the gitops repo, so the code default is the safety net: a
missing env var must never enable either in production.
"""

import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "field", ["TEST_LOGIN_ROUTE_ENABLED", "DEBUG_STACK_TRACE_ENABLED"]
)
def test_debug_flags_default_to_false(field):
    """Asserts the declared field default rather than ``Settings()`` so the
    check is independent of the test environment's values.
    """
    assert Settings.model_fields[field].default is False


def test_elasticsearch_default_host_is_localhost():
    """A typo here made a missing setting look like a DNS failure (#3185)."""
    assert (
        Settings.model_fields["ELASTICSEARCH_HOSTS"].default == "https://localhost:9200"
    )
