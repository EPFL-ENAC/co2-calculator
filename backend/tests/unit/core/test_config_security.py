"""Regression test: the DEBUG setting must default to False in code.

DEBUG is security-critical. It controls the OAuth session cookie's Secure
flag (`app/main.py`: ``https_only=not settings.DEBUG``) and whether the
``/login-test`` auth-bypass route is registered (`app/api/v1/auth.py`). One
image ships to dev/stage/prod with DEBUG set per-environment in the gitops
repo, so the code default is the safety net: it must stay False so a missing
or empty ``DEBUG`` env var can never silently enable debug behaviour in
production.
"""

from app.core.config import Settings


def test_debug_defaults_to_false():
    """The DEBUG field default must be False (fail-safe for stage/prod).

    Asserts the declared field default rather than ``Settings().DEBUG`` so the
    check is independent of whatever DEBUG is set to in the test environment —
    it pins the source-code default, which is the thing that must not regress.
    """
    assert Settings.model_fields["DEBUG"].default is False
