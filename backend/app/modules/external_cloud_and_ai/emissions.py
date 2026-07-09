"""Emission resolution for external cloud and AI entries."""

from app.modules.emissions.buckets import StatBucket
from app.modules.emissions.taxonomy import EmissionType

STAT_BUCKETS: tuple[StatBucket, ...] = (
    StatBucket(key="external_cloud_and_ai", scope=3, roots=(EmissionType.external,)),
)

_CLOUD_SUBKIND_MAP: dict[str, EmissionType] = {
    "virtualisation": EmissionType.external__clouds__virtualisation,
    "compute": EmissionType.external__clouds__calcul,
    "storage": EmissionType.external__clouds__stockage,
}

_AI_USE_MAP: dict[str, EmissionType] = {
    "google": EmissionType.external__ai__provider_google,
    "mistral_ai": EmissionType.external__ai__provider_mistral_ai,
    "anthropic": EmissionType.external__ai__provider_anthropic,
    "openai": EmissionType.external__ai__provider_openai,
    "cohere": EmissionType.external__ai__provider_cohere,
    "others": EmissionType.external__ai__provider_others,
}


def resolve_clouds(data: dict) -> list[EmissionType] | None:
    service_type = (data.get("service_type") or "").lower()
    emission_type = _CLOUD_SUBKIND_MAP.get(service_type)
    return [emission_type] if emission_type else None


def resolve_ai(data: dict) -> list[EmissionType]:
    ai_provider = (data.get("provider") or "").lower().replace(" ", "_")
    emission_type = _AI_USE_MAP.get(ai_provider)
    if emission_type:
        return [emission_type]
    return [EmissionType.external__ai__provider_others]
