from __future__ import annotations

from typing import Any, Callable

from scoring import clamp_open_interval
from .easy_task import grade_easy
from .hard_task import grade_hard
from .medium_task import grade_medium


class BaseTaskGrader:
    score_fn: Callable[[Any], float]

    def grade(self, observation: Any = None) -> float:
        try:
            raw_score = float(self.score_fn(observation))
        except Exception:
            raw_score = 0.02
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
