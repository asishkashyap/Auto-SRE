from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    severity: str
    kind: str
    namespace: str
    resource: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "kind": self.kind,
            "namespace": self.namespace,
            "resource": self.resource,
            "message": self.message,
        }
