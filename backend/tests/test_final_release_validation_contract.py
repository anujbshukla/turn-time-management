from pathlib import Path


def test_final_release_validation_is_non_mutating_for_optimizer():
    root = Path(__file__).parents[2]
    script = (
        root
        / "scripts"
        / "final_release_validation.ps1"
    ).read_text(encoding="utf-8")

    assert "/api/optimization/preview" in script
    assert "/api/optimization/scenario" in script
    assert "/missions/accept" not in script
    assert "/missions/run" not in script
    assert "/status" not in script.split(
        "Checking coordinated recovery optimizer preview"
    )[1]


def test_final_release_validation_covers_readiness_and_ml_governance():
    root = Path(__file__).parents[2]
    script = (
        root
        / "scripts"
        / "final_release_validation.ps1"
    ).read_text(encoding="utf-8")

    assert "/health/readiness" in script
    assert "/api/ml/monitoring" in script
    assert "/api/ml/registry" in script
    assert "/api/optimization/learning/action-effectiveness" in script
