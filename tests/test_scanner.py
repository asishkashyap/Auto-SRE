import json

from auto_sre.scanner import scan_namespace


def test_scan_reports_unhealthy_pod_and_warning_event():
    payloads = {
        "pods": {
            "items": [{
                "metadata": {"name": "api-1"},
                "status": {
                    "phase": "Pending",
                    "containerStatuses": [{"state": {"waiting": {"reason": "ImagePullBackOff"}}}],
                },
            }]
        },
        "events": {
            "items": [{
                "type": "Warning",
                "reason": "FailedScheduling",
                "note": "Insufficient memory",
                "regarding": {"kind": "Pod", "name": "api-1"},
            }]
        },
    }

    def runner(command: list[str]) -> str:
        return json.dumps(payloads[command[2]])

    findings = scan_namespace("auto-sre", runner)

    assert len(findings) == 3
    assert findings[0].message == "Pod phase is Pending"
    assert findings[1].message == "Container waiting: ImagePullBackOff"
    assert findings[2].message == "FailedScheduling: Insufficient memory"


def test_scan_returns_no_findings_for_healthy_namespace():
    payloads = {"pods": {"items": [{"status": {"phase": "Running"}}]}, "events": {"items": []}}

    def runner(command: list[str]) -> str:
        return json.dumps(payloads[command[2]])

    assert scan_namespace(runner=runner) == []


def test_scan_supports_legacy_event_fields():
    payloads = {
        "pods": {"items": []},
        "events": {
            "items": [{
                "type": "Warning",
                "reason": "Unhealthy",
                "message": "Readiness probe failed",
                "involvedObject": {"kind": "Pod", "name": "api-1"},
            }]
        },
    }

    def runner(command: list[str]) -> str:
        return json.dumps(payloads[command[2]])

    findings = scan_namespace("auto-sre", runner)

    assert findings[0].resource == "Pod/api-1"
    assert findings[0].message == "Unhealthy: Readiness probe failed"
