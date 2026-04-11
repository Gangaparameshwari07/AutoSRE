from __future__ import annotations

from typing import Any

from graders import grade_submission


class _TaskGrader:
    task_id: str = ""

    def grade(self, observation: Any = None, *args: Any, **kwargs: Any) -> float:
        final_obs = kwargs.pop("final_obs", kwargs.pop("observation", observation))
        steps = kwargs.pop("steps", kwargs.pop("steps_taken", 10))
        return grade_submission(self.task_id, final_obs, steps)


class EasyGrader(_TaskGrader):
    task_id = "task_1_easy"


class MediumGrader(_TaskGrader):
    task_id = "task_2_medium"


class HardGrader(_TaskGrader):
    task_id = "task_3_hard"


class RecoveryGrader(_TaskGrader):
    task_id = "task_4_recovery"


class EdgeGrader(_TaskGrader):
    task_id = "task_5_edge_database_crash"
