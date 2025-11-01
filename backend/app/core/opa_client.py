"""Open Policy Agent (OPA) client for authorization decisions."""

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OPAClient:
    """Client for interacting with Open Policy Agent."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 1.0):
        """
        Initialize OPA client.

        Args:
            base_url: OPA service URL (defaults to settings.OPA_URL)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or settings.OPA_URL
        self.timeout = timeout
        self.enabled = settings.OPA_ENABLED

    def query(self, policy_path: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query OPA for authorization decision.

        Args:
            policy_path: OPA policy path (e.g., "authz/resource/decision")
            input_data: Input data for policy evaluation

        Returns:
            Policy decision result

        Example:
            >>> opa = OPAClient()
            >>> decision = opa.query(
            ...     "authz/resource/decision",
            ...     {
            ...         "action": "read",
            ...         "resource": "resource",
            ...         "user": {"id": "123", "roles": ["user"]},
            ...     },
            ... )
            >>> print(decision["allow"])
        """
        if not self.enabled:
            logger.warning("OPA is disabled, returning default allow=True")
            return {"allow": True, "filters": {}}

        url = f"{self.base_url}/v1/data/{policy_path}"
        payload = {"input": input_data}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

                if "result" not in result:
                    logger.error(f"OPA response missing 'result' key: {result}")
                    return {"allow": False, "reason": "Invalid OPA response"}

                return result["result"]

        except httpx.TimeoutException:
            logger.error(f"OPA request timeout after {self.timeout}s")
            # Fail closed: deny access on timeout
            return {"allow": False, "reason": "Authorization service timeout"}

        except httpx.HTTPStatusError as e:
            logger.error(
                f"OPA HTTP error: {e.response.status_code} - {e.response.text}"
            )
            return {
                "allow": False,
                "reason": f"Authorization service error: {e.response.status_code}",
            }

        except Exception as e:
            logger.error(f"Unexpected OPA error: {str(e)}", exc_info=True)
            return {"allow": False, "reason": "Authorization service error"}

    async def query_async(
        self, policy_path: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Query OPA asynchronously.

        Args:
            policy_path: OPA policy path
            input_data: Input data for policy evaluation

        Returns:
            Policy decision result
        """
        if not self.enabled:
            logger.warning("OPA is disabled, returning default allow=True")
            return {"allow": True, "filters": {}}

        url = f"{self.base_url}/v1/data/{policy_path}"
        payload = {"input": input_data}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

                if "result" not in result:
                    logger.error(f"OPA response missing 'result' key: {result}")
                    return {"allow": False, "reason": "Invalid OPA response"}

                return result["result"]

        except httpx.TimeoutException:
            logger.error(f"OPA request timeout after {self.timeout}s")
            return {"allow": False, "reason": "Authorization service timeout"}

        except httpx.HTTPStatusError as e:
            logger.error(f"OPA HTTP error: {e.response.status_code}")
            return {
                "allow": False,
                "reason": f"Authorization service error: {e.response.status_code}",
            }

        except Exception as e:
            logger.error(f"Unexpected OPA error: {str(e)}", exc_info=True)
            return {"allow": False, "reason": "Authorization service error"}


# Singleton instance
_opa_client: Optional[OPAClient] = None


def get_opa_client() -> OPAClient:
    """Get or create OPA client singleton."""
    global _opa_client
    if _opa_client is None:
        _opa_client = OPAClient()
    return _opa_client


async def query_opa(policy_path: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to query OPA.

    Args:
        policy_path: OPA policy path
        input_data: Input data for policy evaluation

    Returns:
        Policy decision result
    """
    client = get_opa_client()
    return client.query(policy_path, input_data)
