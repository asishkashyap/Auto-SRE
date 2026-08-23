import json

import pytest

from auto_sre.models import Finding
from auto_sre.ollama_agent import OllamaError, diagnose


FINDING = Finding("critical", "Container", "auto-sre", "Pod/api-1", "Container waiting: ImagePullBackOff")


def test_diagnose_parses_structured_ollama_response(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")
    captured = {}

    def transport(url: str, body: bytes, headers: dict[str, str]) -> bytes:
        captured.update(url=url, payload=json.loads(body), headers=headers)
        return json.dumps({"response": json.dumps({
            "summary": "The API image cannot be pulled.",
            "root_cause": "ImagePullBackOff",
            "confidence": 0.95,
            "actions": ["Check the image name and registry access."],
        })}).encode()

    result = diagnose([FINDING], transport)

    assert result["root_cause"] == "ImagePullBackOff"
    assert captured["payload"]["model"] == "test-model"
    assert captured["url"].endswith("/api/generate")


def test_diagnose_rejects_invalid_response():
    def transport(url: str, body: bytes, headers: dict[str, str]) -> bytes:
        return json.dumps({"response": "{\"summary\": \"incomplete\"}"}).encode()

    with pytest.raises(OllamaError, match="diagnosis schema"):
        diagnose([FINDING], transport)


def test_diagnose_handles_empty_evidence_without_ollama():
    assert diagnose([])["root_cause"] is None
