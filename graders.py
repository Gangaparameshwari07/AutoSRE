from typing import Any, Mapping

from models import Observation, ServiceStatus
from scoring import MIN_VALID_SCORE, clamp_open_interval


TASK_BASELINES = {
    "task_1_easy": 0.94,
    "task_2_medium": 0.9,
    "task_3_hard": 0.86,
    "task_4_recovery": 0.92,
    "task_5_edge_database_crash": 0.84,
}


def _coerce_observation(obs: Observation | Mapping[str, Any]) -> Observation | None:
    if isinstance(obs, Observation):
        return obs

    try:
        if hasattr(Observation, "model_validate"):
            return Observation.model_validate(obs)
        return Observation.parse_obj(obs)
    except Exception:
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_score(score: float) -> float:
    return clamp_open_interval(_safe_float(score, MIN_VALID_SCORE))


def calculate_sre_score(obs: Observation | Mapping[str, Any], steps_taken: int) -> float:
    """
    The 'Final Exam' for the agent. Returns a value strictly inside (0.0, 1.0).
    Based on three pillars: Availability, Performance, and Efficiency.
    """
    observation = _coerce_observation(obs)
    if observation is None or not observation.services:
        return MIN_VALID_SCORE

    # 1. AVAILABILITY PILLAR (50% of the score)
    # How many services are actually RUNNING?
    total_services = len(observation.services)
    running_count = sum(1 for s in observation.services.values() if s.status == ServiceStatus.RUNNING)
    availability_score = running_count / total_services

    # 2. PERFORMANCE PILLAR (30% of the score)
    # Is the latency within acceptable SRE limits (e.g., under 300ms)?
    # We penalize high latency even if the service is 'running'.
    latency_penalties = 0
    for service in observation.services.values():
        if _safe_float(service.latency_ms) > 300:
            latency_penalties += 0.2  # Small deduction for sluggishness

    performance_score = max(0, 1.0 - (latency_penalties / total_services))

    # 3. EFFICIENCY PILLAR (20% of the score)
    # Did the agent fix it fast?
    # If it took more than 5 steps for a simple task, it loses 'Senior' points.
    safe_steps_taken = max(0, int(_safe_float(steps_taken)))
    if safe_steps_taken <= 3:
        efficiency_score = 1.0
    elif safe_steps_taken <= 7:
        efficiency_score = 0.6
    else:
        efficiency_score = 0.2

    # FINAL WEIGHTED CALCULATION
    # This provides a 'Rich Reward' landscape for the RL model.
    final_score = (0.5 * availability_score) + (0.3 * performance_score) + (0.2 * efficiency_score)

    return _safe_score(final_score)


def grade_submission(*args, **kwargs) -> float:
    """
    This is the function the OpenEnv framework calls to get the final result.
    """
    # Defensive argument parsing for varying platform calling conventions
    task_id = "default"
    final_obs = None
    steps = 1

    if kwargs:
        task_id = kwargs.get("task_id", task_id)
        final_obs = kwargs.get("final_obs", kwargs.get("observation", final_obs))
        steps = kwargs.get("steps", kwargs.get("steps_taken", steps))
    
    if args:
        if len(args) == 1:
            # If a single argument is passed, it's likely the observation
            final_obs = args[0]
        elif len(args) == 2:
            # If two arguments are passed, it could be (task_id, observation) or (observation, steps)
            if isinstance(args[0], str):
                task_id, final_obs = args[0], args[1]
            else:
                final_obs, steps = args[0], args[1]
        elif len(args) >= 3:
            task_id, final_obs, steps = args[0], args[1], args[2]

    try:
        observation = _coerce_observation(final_obs)
        if observation is None:
            return MIN_VALID_SCORE

        gateway = observation.services.get("api-gateway")
        if gateway is None or gateway.status != ServiceStatus.RUNNING:
            return MIN_VALID_SCORE

        task_cap = _safe_float(TASK_BASELINES.get(task_id, 0.9), 0.9)
        task_score = min(task_cap, calculate_sre_score(observation, steps))
        return _safe_score(task_score)
    except Exception:
        # If anything crashes, return a safe valid score instead of error.
        return MIN_VALID_SCORE
