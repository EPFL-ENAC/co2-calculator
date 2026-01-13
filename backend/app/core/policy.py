async def query_policy(policy_name: str, input: dict) -> dict:
    """
    Query resources based on provided filters.

    """
    authorized_names = ["resource:query", "unit:query"]
    if policy_name not in authorized_names:
        raise ValueError("Unsupported policy name for query_policy")
    # For simplicity, we directly apply filters in the repository
    filters = input.get("filters", None)
    return {
        "allow": True if filters is not None else False,
        "reason": "Filtered query" if filters else "No filters",
        "filters": {},
    }
