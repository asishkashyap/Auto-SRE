import argparse
import json

from .scanner import scan_namespace
from .ollama_agent import OllamaError, diagnose


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-sre", description="Inspect Kubernetes reliability signals")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="scan a namespace for unhealthy Pods and warning Events")
    scan.add_argument("--namespace", default="auto-sre")
    scan.add_argument("--json", action="store_true", dest="as_json")
    diagnosis = subparsers.add_parser("diagnose", help="scan a namespace and ask local Ollama for a structured diagnosis")
    diagnosis.add_argument("--namespace", default="auto-sre")
    diagnosis.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "scan":
        return _scan_command(args.namespace, args.as_json)
    if args.command == "diagnose":
        return _diagnose_command(args.namespace, args.as_json)
    return 1


def _scan_command(namespace: str, as_json: bool) -> int:
    try:
        findings = scan_namespace(namespace)
    except Exception as error:
        print(f"scan failed: {error}")
        return 1
    if as_json:
        print(json.dumps([finding.as_dict() for finding in findings], indent=2))
    elif findings:
        for finding in findings:
            print(f"[{finding.severity.upper()}] {finding.kind} {finding.namespace}/{finding.resource}: {finding.message}")
    else:
        print(f"No findings in namespace {namespace}")
    return 2 if any(finding.severity == "critical" for finding in findings) else 0


def _diagnose_command(namespace: str, as_json: bool) -> int:
    try:
        result = diagnose(scan_namespace(namespace))
    except (OllamaError, OSError, ValueError) as error:
        print(f"diagnosis failed: {error}")
        return 1
    print(json.dumps(result, indent=2) if as_json else result["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
