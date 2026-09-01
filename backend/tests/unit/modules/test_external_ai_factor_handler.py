"""Regression tests for #2587: an unknown AI provider in a factor payload
must give a readable error, not a bare KeyError.
"""

import pytest

from app.modules.emissions.taxonomy import EmissionType, EmissionTypeResolutionError
from app.modules.external_cloud_and_ai.factors import ExternalAIFactorHandler


def _payload(**overrides: object) -> dict:
    payload: dict = {
        "provider": "Mistral AI",
        "usage_type": "text",
        "ef_kg_co2eq_per_request": 0.0075,
    }
    payload.update(overrides)
    return payload


def test_known_provider_resolves_its_emission_type() -> None:
    handler = ExternalAIFactorHandler()
    dto = handler.validate_create(_payload())
    assert dto.emission_type_id == EmissionType.external__ai__provider_mistral_ai.value


def test_unknown_provider_raises_readable_error_not_keyerror() -> None:
    handler = ExternalAIFactorHandler()
    with pytest.raises(EmissionTypeResolutionError, match="doesnotexist"):
        handler.validate_create(_payload(provider="doesnotexist"))


def test_error_lists_the_accepted_providers() -> None:
    handler = ExternalAIFactorHandler()
    with pytest.raises(EmissionTypeResolutionError, match="mistral_ai"):
        handler.validate_create(_payload(provider="Deepseek"))


def test_explicit_emission_type_id_is_kept() -> None:
    handler = ExternalAIFactorHandler()
    dto = handler.validate_create(
        _payload(emission_type_id=EmissionType.external__ai.value)
    )
    assert dto.emission_type_id == EmissionType.external__ai.value
