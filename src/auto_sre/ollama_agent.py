import json
import os
from collections.abc import Callable
from urllib import request

from .models import Finding

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
Transport = Callable[[str, bytes, dict[str, str]], bytes]


class OllamaError(RuntimeError):
    """Raised when the local Ollama agent cannot produce a diagnosis."""


def diagnose(findings: list[Finding], transport: Transport | None = None) -> dict:
    if not findings:
        return {
            "summary": "No active Kubernetes findings were provided.",
            "root_cause": None,
            "confidence": 1.0,
            "actions": [],
        }

    payload = {
        "model": os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        "stream": False,
        "format": "json",
        "prompt": _prompt(findings),
    }
    body = json.dumps(payload).encode("utf-8")
    send = transport or _transport
    try:
        response = send(
            f"{os.getenv('OLLAMA_URL', DEFAULT_OLLAMA_URL).rstrip('/')}/api/generate",
            body,
            {"Content-Type": "application/json"},
        )
        result = json.loads(response)
        diagnosis = json.loads(result["response"])
    except (KeyError, OSError, ValueError) as error:
        raise OllamaError(f"Ollama diagnosis failed: {error}") from error

    _validate_diagnosis(diagnosis)
    return diagnosis


def _prompt(findings: list[Finding]) -> str:
    evidence = json.dumps([finding.as_dict() for finding in findings], indent=2)
    return (
        "You are a Kubernetes SRE assistant. Analyze only the supplied evidence. "
        "Do not invent observations and do not suggest arbitrary shell commands. "
        "Return JSON with exactly these keys: summary (string), root_cause (string or null), "
        "confidence (number from 0 to 1), actions (array of strings). Evidence:\n" + evidence
    )


def _validate_diagnosis(diagnosis: dict) -> None:
    required = {"summary", "root_cause", "confidence", "actions"}
    if set(diagnosis) != required:
        raise OllamaError("Ollama response did not match the diagnosis schema")
    if not isinstance(diagnosis["summary"], str) or not isinstance(diagnosis["actions"], list):
        raise OllamaError("Ollama response has invalid diagnosis field types")
    if not isinstance(diagnosis["confidence"], (int, float)) or not 0 <= diagnosis["confidence"] <= 1:
        raise OllamaError("Ollama confidence must be between 0 and 1")


def _transport(url: str, body: bytes, headers: dict[str, str]) -> bytes:
    try:
        with request.urlopen(request.Request(url, data=body, headers=headers, method="POST"), timeout=60) as response:
            return response.read()
    except OSError as error:
        raise OllamaError(f"Cannot reach Ollama at {url}. Start Ollama and pull the configured model.") from error
