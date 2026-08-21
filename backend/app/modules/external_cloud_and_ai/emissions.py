"""Emission resolution for external cloud and AI entries."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import (
    EmissionType,
    EmissionTypeResolutionError,
    canonical_token,
)

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(key="external_cloud_and_ai", scope=3, roots=(EmissionType.external,)),
)

_CLOUD_SUBKIND_MAP: dict[str, EmissionType] = {
    "virtualisation": EmissionType.external__clouds__virtualisation,
    "compute": EmissionType.external__clouds__calcul,
    "storage": EmissionType.external__clouds__stockage,
}

# Keyed on ``canonical_token`` output. Both spellings are declared: the
# vendor name, and the product-name form the EPFL CSVs actually carry
# ("Claude (Anthropic)" -> claude_anthropic). Before #2091 only
# ``mistral_ai`` happened to match, so 16 of 19 factor rows disappeared
# into ``provider_others`` and the AI breakdown chart read as one bucket.
_AI_USE_MAP: dict[str, EmissionType] = {
    "google": EmissionType.external__ai__provider_google,
    "gemini_google": EmissionType.external__ai__provider_google,
    "mistral_ai": EmissionType.external__ai__provider_mistral_ai,
    "anthropic": EmissionType.external__ai__provider_anthropic,
    "claude_anthropic": EmissionType.external__ai__provider_anthropic,
    "openai": EmissionType.external__ai__provider_openai,
    "chatgpt_openai": EmissionType.external__ai__provider_openai,
    "cohere": EmissionType.external__ai__provider_cohere,
    "github": EmissionType.external__ai__provider_github,
    "copilot_github": EmissionType.external__ai__provider_github,
    "microsoft": EmissionType.external__ai__provider_microsoft,
    "copilot_microsoft": EmissionType.external__ai__provider_microsoft,
    "other": EmissionType.external__ai__provider_others,
    "others": EmissionType.external__ai__provider_others,
}


def resolve_clouds(data: dict) -> list[EmissionType]:
    service_type = (data.get("service_type") or "").lower()
    emission_type = _CLOUD_SUBKIND_MAP.get(service_type)
    if emission_type is None:
        raise EmissionTypeResolutionError(
            f"No emission type for cloud service_type {service_type!r} — "
            f"expected one of {sorted(_CLOUD_SUBKIND_MAP)}"
        )
    return [emission_type]


def resolve_ai(data: dict) -> list[EmissionType]:
    """``provider_others`` is reachable only when the CSV says "others".

    #2091: it used to absorb every unrecognised provider, so a new vendor
    or a typo disappeared into a bucket nobody audits. It stays a real
    leaf — the CSV just has to name it.
    """
    ai_provider = canonical_token(data.get("provider"))
    emission_type = _AI_USE_MAP.get(ai_provider)
    if emission_type is None:
        raise EmissionTypeResolutionError(
            f"No emission type for AI provider {ai_provider!r} — "
            f"expected one of {sorted(_AI_USE_MAP)}"
        )
    return [emission_type]
