from tasks.graders import BaseTaskGrader, EasyGrader, HardGrader, MediumGrader

__all__ = ["BaseTaskGrader", "EasyGrader", "MediumGrader", "HardGrader", "grade_submission", "calculate_sre_score"]

def grade_submission(task_id: str, final_observation, steps: int) -> float:
    from tasks.graders import EasyGrader, MediumGrader, HardGrader
    
    graders = {
        "task_1_easy": EasyGrader,
        "task_2_medium": MediumGrader,
        "task_3_hard": HardGrader,
    }
    grader_cls = graders.get(task_id)
    if not grader_cls:
        return 0.01
    return grader_cls().grade(final_observation)

def calculate_sre_score(obs, steps: int) -> float:
    if hasattr(obs, "system_health_score"):
        return min(0.99, max(0.01, float(obs.system_health_score)))
    if isinstance(obs, dict) and "system_health_score" in obs:
        return min(0.99, max(0.01, float(obs.get("system_health_score", 0.01))))
    return 0.99
    

