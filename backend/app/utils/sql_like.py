"""LIKE/ILIKE pattern helpers shared by the search repositories."""


def escape_like(term: str) -> str:
    r"""Escape LIKE metacharacters so user input matches literally.

    Callers must pass ``escape="\\"`` to the ``like``/``ilike`` built from
    the result, otherwise the escaping backslashes stay literal.
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
