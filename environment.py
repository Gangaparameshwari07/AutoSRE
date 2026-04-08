import asyncio
import random
from typing import Dict, List, NamedTuple
from models import Service, ServiceStatus, LogEntry, Observation, Action
from scoring import clamp_open_interval

# 1. We keep StepResult but use it to return a single object to satisfy Amazon Q
class StepResult(NamedTuple):
    observation: Observation
    reward: float
    done: bool
    info: dict

class AutoSREEnv:
    def __init__(self):
        self.service_names = ["api-gateway", "auth-service", "order-service", "payment-service", "database"]
        self.reset()

    def reset(self, task_id: str = "default") -> Observation:
        self.services: Dict[str, Service] = {}
        for name in self.service_names:
            self.services[name] = Service(
                name=name,
                status=ServiceStatus.RUNNING,
                cpu_usage=20.0,
                mem_usage=30.0,
                latency_ms=50.0,
                error_rate=0.0
            )
        self.logs: List[LogEntry] = [LogEntry(timestamp="now", level="INFO", service="system", message="Cluster initialized")]
        self.step_count = 0
        
        from definitions import apply_task_scenario, TASKS
        if task_id in TASKS:
            apply_task_scenario(self, task_id)
            self.task_description = TASKS[task_id]["description"]
        else:
            self.task_description = "Maintain system health."

        self._apply_cascade_effects()
        return self._get_observation()

    def _get_observation(self) -> Observation:
        total_health = sum([1.0 if s.status == ServiceStatus.RUNNING else 0.5 if s.status == ServiceStatus.DEGRADED else 0.0 for s in self.services.values()])
        raw_health_score = total_health / len(self.service_names)
        health_score = clamp_open_interval(raw_health_score)
        
        return Observation(
            services=self.services,
            recent_logs=self.logs[-5:], 
            system_health_score=health_score,
            alerts=[l.message for l in self.logs if l.level in ["ERROR", "CRITICAL"]][-3:],
            task_description=self.task_description
        )

    def _raw_health_score(self) -> float:
        total_health = sum(
            [
                1.0 if s.status == ServiceStatus.RUNNING else 0.5 if s.status == ServiceStatus.DEGRADED else 0.0
                for s in self.services.values()
            ]
        )
        return total_health / len(self.service_names)

    def state(self) -> Observation:
        """Return the current environment state for validators and control plane clients."""
        return self._get_observation()

    def _apply_cascade_effects(self):
        """Apply dependency failures while preserving service-specific incidents."""
        db = self.services["database"]
        auth = self.services["auth-service"]
        gateway = self.services["api-gateway"]
        auth_has_local_issue = auth.mem_usage > 85.0 or auth.cpu_usage > 90.0

        # 1. Database -> Auth Cascade
        if db.status != ServiceStatus.RUNNING or db.latency_ms > 500:
            auth.status = ServiceStatus.DEGRADED
            auth.latency_ms = max(auth.latency_ms, 250.0)
            auth.error_rate = max(auth.error_rate, 0.4)
        else:
            # Only heal auth if its own metrics are healthy.
            if auth.status != ServiceStatus.CRASHED and not auth_has_local_issue:
                auth.status = ServiceStatus.RUNNING
                auth.latency_ms = min(auth.latency_ms, 50.0)
                auth.error_rate = 0.0
        
        # 2. Auth -> Gateway Cascade
        if auth.status != ServiceStatus.RUNNING:
            gateway.status = ServiceStatus.CRASHED
            gateway.error_rate = 1.0
            gateway.latency_ms = max(gateway.latency_ms, 300.0)
        else:
            # If Auth is healthy, Gateway can recover
            if gateway.status == ServiceStatus.CRASHED:
                gateway.status = ServiceStatus.RUNNING
                gateway.error_rate = 0.0
                gateway.latency_ms = 50.0

    def step(self, action: Action) -> StepResult:
        """Processes the agent's action and updates the world state."""
        target = action.target_service
        
        if action.action_type == "restart_service" and target in self.services:
            svc = self.services[target]
            svc.status = ServiceStatus.RUNNING
            svc.error_rate = 0.0
            svc.latency_ms = 50.0
            svc.cpu_usage = min(svc.cpu_usage, 30.0)
            svc.mem_usage = min(svc.mem_usage, 40.0)
            self.logs.append(LogEntry(timestamp="now", level="INFO", service=target, message=f"Restarted {target}"))
            
        elif action.action_type == "scale_up" and target in self.services:
            svc = self.services[target]
            svc.cpu_usage = max(10.0, svc.cpu_usage - 40.0)
            svc.mem_usage = max(20.0, svc.mem_usage - 30.0)
            svc.latency_ms = max(40.0, svc.latency_ms - 500.0)
            svc.error_rate = max(0.0, svc.error_rate - 0.3)
            svc.status = ServiceStatus.RUNNING
            self.logs.append(LogEntry(timestamp="now", level="INFO", service=target, message=f"Scaled {target}"))

        elif action.action_type == "clear_cache" and target in self.services:
            svc = self.services[target]
            svc.mem_usage = max(20.0, svc.mem_usage - 50.0)
            svc.latency_ms = max(50.0, svc.latency_ms - 150.0)
            svc.error_rate = max(0.0, svc.error_rate - 0.2)
            if svc.status != ServiceStatus.CRASHED and svc.mem_usage < 85.0:
                svc.status = ServiceStatus.RUNNING
            self.logs.append(LogEntry(timestamp="now", level="INFO", service=target, message=f"Cleared cache on {target}"))

        elif action.action_type == "rollback" and target in self.services:
            svc = self.services[target]
            svc.error_rate = max(0.0, svc.error_rate - 0.5)
            svc.latency_ms = max(50.0, svc.latency_ms - 100.0)
            if svc.status == ServiceStatus.DEGRADED and svc.error_rate < 0.2:
                svc.status = ServiceStatus.RUNNING
            self.logs.append(LogEntry(timestamp="now", level="INFO", service=target, message=f"Rolled back {target}"))

        elif action.action_type == "scale_down" and target in self.services:
            svc = self.services[target]
            svc.cpu_usage = min(100.0, svc.cpu_usage + 10.0)
            svc.mem_usage = min(100.0, svc.mem_usage + 10.0)
            svc.latency_ms = min(1000.0, svc.latency_ms + 50.0)
            if svc.cpu_usage > 90.0 or svc.mem_usage > 90.0:
                svc.status = ServiceStatus.DEGRADED
            self.logs.append(LogEntry(timestamp="now", level="WARN", service=target, message=f"Scaled down {target}"))

        elif action.action_type == "noop":
            self.logs.append(LogEntry(timestamp="now", level="INFO", service=target, message="No action taken"))

        # Re-evaluate system state
        self._apply_cascade_effects()

        self.step_count += 1
        obs = self._get_observation()
        
        # We return a single StepResult object. 
        # Using keywords (observation=obs) stops the Amazon Q warning.
        return StepResult(
            observation=obs,
            reward=clamp_open_interval(obs.system_health_score),
            done=(self.step_count >= 10 or self._raw_health_score() >= 0.98),
            info={}
        )
