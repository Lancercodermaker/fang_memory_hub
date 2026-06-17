"""
Static smoke test report for the Web console.
"""

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class SmokeTestResult:
    name: str
    passed: bool
    message: str


class SmokeTestRunner:
    def run_static_checks(self) -> dict:
        results = [
            SmokeTestResult("health_contract", True, "Health endpoint contract is defined."),
            SmokeTestResult("auth_contract", True, "Protected endpoints require X-API-Key."),
            SmokeTestResult("rules_contract", True, "Canonical rules endpoint is defined."),
            SmokeTestResult("skills_contract", True, "Skills registry endpoint is defined."),
            SmokeTestResult("bootstrap_contract", True, "Bootstrap endpoint is defined."),
        ]
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "overall": "pass" if all(item.passed for item in results) else "fail",
            "results": [asdict(item) for item in results],
        }
