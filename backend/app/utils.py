"""utils.py — Shared utility functions."""

import numpy as np


def sanitize_for_json(obj):
    """
    Recursively convert numpy scalar types to Python native types so FastAPI
    can serialize the response without errors.

    Handles: numpy.bool_, numpy.integer, numpy.floating, NaN, Inf.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj
