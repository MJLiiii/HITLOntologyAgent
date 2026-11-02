"""Bounded, ordered cursor pagination for already authorized records."""
from ..errors import Problem


def page(items, cursor: str | None, limit: int):
    if limit < 1 or limit > 200:
        raise Problem(422, "invalid_limit", "Limit must be between 1 and 200")
    start = 0
    if cursor:
        indices = [i for i, value in enumerate(items) if value["id"] == cursor]
        if not indices:
            raise Problem(422, "invalid_cursor", "Unknown list cursor")
        start = indices[0] + 1
    selected = items[start:start + limit]
    return {"items": selected, "next_cursor": selected[-1]["id"] if start + limit < len(items) else None}
