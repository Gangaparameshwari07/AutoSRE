from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, List, Literal
from enum import Enum

class ServiceStatus(str, Enum):
    RUNNING = "running"
    DEGRADED = "degraded"   # High latency/errors but still up
    CRASHED = "crashed"     # Completely down
    MAINTENANCE = "maintenance"

class Service(BaseModel):
    name: str
    status: ServiceStatus
    cpu_usage: float        # 0.0 to 100.0
    mem_usage: float        # 0.0 to 100.0
    latency_ms: float
    error_rate: float       # 0.0 to 1.0

class LogEntry(BaseModel):
    timestamp: str
    level: Literal["INFO", "WARN", "ERROR", "CRITICAL"]
    service: str
    message: str

class Observation(BaseModel):
    services: Dict[str, Service]
    recent_logs: List[LogEntry]
    system_health_score: float
    alerts: List[str]
    task_description: str


class Reward(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    reason: str = ""

class Action(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action_type: Literal[
        "restart_service", 
        "scale_up", 
        "scale_down", 
        "clear_cache", 
        "rollback", 
        "noop"
    ] = Field(alias="action")
    target_service: str = Field(alias="target")
