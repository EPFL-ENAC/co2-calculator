"""Shared secret authenticating the intra-cluster ``/internal`` endpoints (#2530).

Those endpoints used to be gated on the caller's source IP matching a live
``pods`` row. That gate is only as strong as uvicorn's proxy-header trust, and
the deployed value of ``FORWARDED_ALLOW_IPS`` is ``10.20.0.0/16,10.98.42.0/24``
in dev, stage and prod — ``10.20.0.0/16`` being the cluster's whole pod overlay
subnet. uvicorn's ``proxy_headers`` defaults to *True*, so any workload whose
own address falls in that range is treated as a trusted proxy: its
``X-Forwarded-For`` is honoured, ``scope["client"]`` becomes whatever it says,
and the IP allowlist is satisfied by a header. This token is the part of the
request a caller cannot choose.

Derived from ``JWT_HMAC_KEY`` rather than provisioned as its own secret: every
pod already has that key, so the gate is real the moment the image ships. A
gate that only closes after someone remembers an ops action is a gate that
ships open. HMAC-SHA256 is one-way, so the token cannot be walked back to the
signing key it is derived from, and the label keeps the two signing domains
separate.
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

    Fails closed on a missing header and on an unset ``JWT_HMAC_KEY`` — an
    empty key would otherwise derive a token anyone can compute. Outside local
    dev the key is already required at boot (``assert_security_settings``).
    """
    if not presented or not get_settings().JWT_HMAC_KEY:
        return False
    return hmac.compare_digest(presented, internal_auth_token())
