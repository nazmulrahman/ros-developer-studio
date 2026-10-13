from fastapi import HTTPException


def not_implemented(phase: int, what: str):
    """Scaffold marker: endpoint is designed, not built. Never returns fake data."""
    raise HTTPException(501, {"error": "not_implemented", "feature": what, "planned_phase": phase})
