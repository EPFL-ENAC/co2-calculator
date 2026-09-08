"""Shared secret authenticating the intra-cluster ``/internal`` endpoints (#2530).

The old IP-allowlist gate was defeated by the cluster's own proxy-trust
config — any pod can spoof another pod's IP. See the #2530 plan for the full
story. This token is the part of the request a caller cannot choose, derived
from ``JWT_HMAC_KEY`` (not its own secret) so the gate is real on first boot.
"""

import hashlib
import hmac

from app.core.config import get_settings

INTERNAL_AUTH_HEADER = "X-Internal-Auth"

# Domain separation: this token and a JWT are both keyed on JWT_HMAC_KEY, and
# neither may ever be usable as the other.
_DERIVATION_LABEL = b"co2-calculator/internal-api/v1"


def internal_auth_token() -> str:
    """The token every pod can compute and no outside caller can."""
    return hmac.new(
        get_settings().JWT_HMAC_KEY.encode(), _DERIVATION_LABEL, hashlib.sha256
    ).hexdigest()


def internal_auth_ok(presented: str | None) -> bool:
    """True when ``presented`` is this deployment's internal token.

    Fails closed on a missing header or unset ``JWT_HMAC_KEY``. Non-ASCII is
    rejected before comparing: Starlette decodes headers as latin-1, and
    ``compare_digest`` raises TypeError above U+007F — unhandled, that turns
    an unauthenticated request into a 500 instead of a 403.
    """
    if not presented or not presented.isascii():
        return False
    if not get_settings().JWT_HMAC_KEY:
        return False
    return hmac.compare_digest(presented, internal_auth_token())
