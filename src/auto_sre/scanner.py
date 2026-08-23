import json
import subprocess
from collections.abc import Callable

from .models import Finding

Runner = Callable[[list[str]], str]
BENIGN_WAITING_REASONS = {"ContainerCreating", "PodInitializing"}


def kubectl_json(resource: str, namespace: str, runner: Runner) -> dict:
    output = runner(["kubectl", "get", resource, "-n", namespace, "-o", "json"])
    return json.loads(output)


def scan_namespace(namespace: str = "auto-sre", runner: Runner | None = None) -> list[Finding]:
    runner = runner or _run
    pods = kubectl_json("pods", namespace, runner)
    events = kubectl_json("events", namespace, runner)
    return _pod_findings(pods, namespace) + _event_findings(events, namespace)


def _pod_findings(pods: dict, namespace: str) -> list[Finding]:
    findings: list[Finding] = []
    for pod in pods.get("items", []):
        metadata = pod.get("metadata", {})
        name = metadata.get("name", "unknown")
        status = pod.get("status", {})
        phase = status.get("phase", "Unknown")
        waiting_reasons = {
            container.get("state", {}).get("waiting", {}).get("reason")
            for container in status.get("containerStatuses", [])
        }
        if phase not in {"Running", "Succeeded"} and not waiting_reasons.intersection(BENIGN_WAITING_REASONS):
            findings.append(Finding("critical", "Pod", namespace, name, f"Pod phase is {phase}"))
        findings.extend(_container_findings(status, namespace, name))
    return findings


def _container_findings(status: dict, namespace: str, name: str) -> list[Finding]:
    findings: list[Finding] = []
    for container in status.get("containerStatuses", []):
        state = container.get("state", {})
        waiting = state.get("waiting")
        terminated = state.get("terminated")
        if waiting and waiting.get("reason") not in BENIGN_WAITING_REASONS:
            reason = waiting.get("reason", "Waiting")
            findings.append(Finding("critical", "Container", namespace, name, f"Container waiting: {reason}"))
        if terminated and terminated.get("exitCode", 0) != 0:
            reason = terminated.get("reason", "Terminated")
            findings.append(Finding("critical", "Container", namespace, name, f"Container terminated: {reason}"))
    return findings


def _event_findings(events: dict, namespace: str) -> list[Finding]:
    findings: list[Finding] = []
    for event in events.get("items", []):
        if event.get("type") != "Warning":
            continue
        involved = event.get("regarding") or event.get("involvedObject", {})
        resource = f"{involved.get('kind', 'Unknown')}/{involved.get('name', 'unknown')}"
        reason = event.get("reason", "Warning")
        note = event.get("note") or event.get("message", "No details")
        findings.append(Finding("warning", "Event", namespace, resource, f"{reason}: {note}"))
    return findings


def _run(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout
