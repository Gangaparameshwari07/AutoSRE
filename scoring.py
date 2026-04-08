MIN_VALID_SCORE = 0.01
MAX_VALID_SCORE = 0.99


def clamp_open_interval(score: float) -> float:
    """
    Keep all public-facing scores strictly inside the open interval (0, 1).
    """
    bounded = min(MAX_VALID_SCORE, max(MIN_VALID_SCORE, float(score)))
    return round(bounded, 3)
