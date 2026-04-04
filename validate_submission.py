import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv
from fastapi.testclient import TestClient

import definitions
import graders
import inference
import models
from environment import AutoSREEnv
from models import Observation
from server import app


ROOT = Path(__file__).resolve().parent
SERVER_URL = "http://127.0.0.1:7860"
VALIDATOR_SERVER_PORT = "7861"

load_dotenv(ROOT / ".env")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_openenv() -> dict:
    with (ROOT / "openenv.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def check_project_files() -> None:
    assert_true((ROOT / "inference.py").exists(), "Missing root inference.py")
    assert_true((ROOT / "Dockerfile").exists(), "Missing root Dockerfile")
    assert_true((ROOT / "openenv.yaml").exists(), "Missing openenv.yaml")


def check_openenv_yaml() -> None:
    config = load_openenv()
    assert_true(config.get("entry_point") == "server:app", "openenv.yaml entry_point must be server:app")
    runtime = config.get("runtime", {})
    assert_true(runtime.get("port") == 7860, "openenv.yaml runtime.port must be 7860")
    assert_true(runtime.get("resource_limits", {}).get("vcpu") == 2, "openenv.yaml vcpu limit must be 2")
    assert_true(runtime.get("resource_limits", {}).get("memory_gb") == 8, "openenv.yaml memory limit must be 8 GB")
    assert_true(runtime.get("execution_timeout_minutes") == 20, "openenv.yaml timeout must be 20 minutes")


def check_environment_variables() -> None:
    required = ["API_BASE_URL", "MODEL_NAME", "HF_TOKEN"]
    for key in required:
        assert_true(bool(os.getenv(key)), f"Missing required environment variable: {key}")


def check_typed_models() -> None:
    action = models.Action(action="noop", target="api-gateway")
    assert_true(action.action_type == "noop", "Action alias mapping for 'action' failed")
    assert_true(action.target_service == "api-gateway", "Action alias mapping for 'target' failed")
    env = AutoSREEnv()
    obs = env.reset("task_1_easy")
    assert_true(isinstance(obs, Observation), "reset() must return Observation")
    assert_true(isinstance(env.state(), Observation), "state() must return Observation")


def check_control_plane_endpoints() -> None:
    client = TestClient(app)
    reset_response = client.post("/reset", params={"task_id": "task_1_easy"})
    assert_true(reset_response.status_code == 200, "POST /reset must return 200")

    state_response = client.get("/state")
    assert_true(state_response.status_code == 200, "GET /state must return 200")
    state_json = state_response.json()
    assert_true("observation" in state_json, "GET /state must include observation")

    step_response = client.post("/step", json={"action": "restart_service", "target": "payment-service"})
    assert_true(step_response.status_code == 200, "POST /step must return 200")
    step_json = step_response.json()
    assert_true("observation" in step_json, "POST /step must include observation")

    root_response = client.get("/")
    assert_true(root_response.status_code == 200, "GET / must return 200")


def solve_task_with_api(client: TestClient, task_id: str) -> tuple[Observation, int, float]:
    client.post("/reset", params={"task_id": task_id})
    steps = 0
    final_observation = None
    done = False

    while steps < 10 and not done:
        steps += 1
        state_text = client.get("/").text
        action, target = inference._fallback_action(state_text)
        response = client.post("/step", json={"action": action, "target": target})
        payload = response.json()
        final_observation = Observation.model_validate(payload["observation"])
        done = bool(payload.get("done"))

    assert_true(final_observation is not None, f"No observation returned while solving {task_id}")
    score = graders.grade_submission(task_id, final_observation, steps)
    assert_true(0.0 <= score <= 1.0, f"Score out of range for {task_id}: {score}")
    return final_observation, steps, score


def check_tasks_and_graders() -> None:
    assert_true(len(definitions.TASKS) >= 3, "At least 3 tasks are required")
    client = TestClient(app)
    for task_id in definitions.TASKS:
        _, _, score = solve_task_with_api(client, task_id)
        print(f"[PASS] grader score for {task_id}: {score}")


def wait_for_server(timeout_seconds: float = 20.0) -> None:
    server_url = f"http://127.0.0.1:{VALIDATOR_SERVER_PORT}"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = httpx.get(f"{server_url}/state", timeout=2.0)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for server startup on port {VALIDATOR_SERVER_PORT}")


def run_inference_against_live_server() -> None:
    env = os.environ.copy()
    env["PORT"] = VALIDATOR_SERVER_PORT
    env["DASHBOARD_URL"] = f"http://127.0.0.1:{VALIDATOR_SERVER_PORT}"
    server_process = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        wait_for_server()
        result = subprocess.run(
            [sys.executable, "inference.py"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        assert_true(result.returncode == 0, f"inference.py failed:\n{result.stdout}\n{result.stderr}")
        assert_true("[START] task=" in result.stdout, "inference.py missing sample-compliant [START] log")
        assert_true("[STEP] step=" in result.stdout, "inference.py missing sample-compliant [STEP] log")
        assert_true("action=" in result.stdout, "inference.py missing action field in [STEP] log")
        assert_true("[END] success=" in result.stdout, "inference.py missing sample-compliant [END] log")
    finally:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()


def main() -> None:
    check_project_files()
    print("[PASS] required root files present")

    check_openenv_yaml()
    print("[PASS] openenv.yaml validated")

    check_environment_variables()
    print("[PASS] required environment variables detected")

    check_typed_models()
    print("[PASS] typed models and env methods validated")

    check_control_plane_endpoints()
    print("[PASS] control plane endpoints validated")

    check_tasks_and_graders()
    print("[PASS] tasks and graders validated")

    run_inference_against_live_server()
    print("[PASS] inference.py completed successfully against live server")

    print("[PASS] pre-submission validation completed")


if __name__ == "__main__":
    main()
