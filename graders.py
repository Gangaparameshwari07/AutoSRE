from models import Observation, ServiceStatus
from scoring import MIN_VALID_SCORE, clamp_open_interval


TASK_BASELINES = {
    "task_1_easy": 0.94,
    "task_2_medium": 0.9,
    "task_3_hard": 0.86,
}

def calculate_sre_score(obs: Observation, steps_taken: int) -> float:
    """
    The 'Final Exam' for the agent. Returns a value between 0.0 and 1.0.
    Based on three pillars: Availability, Performance, and Efficiency.
    """
    
    # 1. AVAILABILITY PILLAR (50% of the score)
    # How many services are actually RUNNING?
    total_services = len(obs.services)
    running_count = sum(1 for s in obs.services.values() if s.status == ServiceStatus.RUNNING)
    availability_score = running_count / total_services

    # 2. PERFORMANCE PILLAR (30% of the score)
    # Is the latency within acceptable SRE limits (e.g., under 300ms)?
    # We penalize high latency even if the service is 'running'.
    latency_penalties = 0
    for service in obs.services.values():
        if service.latency_ms > 300:
            latency_penalties += 0.2  # Small deduction for sluggishness
    
    performance_score = max(0, 1.0 - (latency_penalties / total_services))

    # 3. EFFICIENCY PILLAR (20% of the score)
    # Did the agent fix it fast? 
    # If it took more than 5 steps for a simple task, it loses 'Senior' points.
    if steps_taken <= 3:
        efficiency_score = 1.0
    elif steps_taken <= 7:
        efficiency_score = 0.6
    else:
        efficiency_score = 0.2

    # FINAL WEIGHTED CALCULATION
    # This provides a 'Rich Reward' landscape for the RL model.
    final_score = (0.5 * availability_score) + (0.3 * performance_score) + (0.2 * efficiency_score)

    return clamp_open_interval(final_score)

def grade_submission(task_id: str, final_obs: Observation, steps: int) -> float:
    """
    This is the function the OpenEnv framework calls to get the final result.
    """
    # If the API Gateway is still crashed, it's an automatic failure (0.0) 
    # because the user can't even access the site.
    if final_obs.services["api-gateway"].status != ServiceStatus.RUNNING:
        return MIN_VALID_SCORE

    task_cap = TASK_BASELINES.get(task_id, 0.9)
    task_score = min(task_cap, calculate_sre_score(final_obs, steps))
    return clamp_open_interval(task_score)
