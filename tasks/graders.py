from __future__ import annotations

from typing import Any, Callable

from scoring import clamp_open_interval


def _fallback_grade(_: Any = None) -> float:
    return 0.01


try:
    from .easy_task import grade_easy
except ImportError:
    grade_easy = _fallback_grade

try:
    from .hard_task import grade_hard
except ImportError:
    grade_hard = _fallback_grade

try:
    from .medium_task import grade_medium
except ImportError:
    grade_medium = _fallback_grade

class BaseTaskGrader:
    score_fn: Callable[[Any], float]

    def grade(self, observation: Any = None) -> float:
        try:
            raw_score = float(self.score_fn(observation))
        except Exception:
            raw_score = 0.01
        return clamp_open_interval(raw_score)

    def result(self, observation: Any = None) -> dict[str, float]:
        score = self.grade(observation)
        return {"score": score, "reward": score}


class EasyGrader(BaseTaskGrader):
    score_fn = staticmethod(grade_easy)


class MediumGrader(BaseTaskGrader):
    score_fn = staticmethod(grade_medium)


class HardGrader(BaseTaskGrader):
    score_fn = staticmethod(grade_hard)
