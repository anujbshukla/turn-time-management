from pathlib import Path


def test_mission_learning_demo_seed_has_safety_contract():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "seed_mission_learning_demo.py"
    )
    source = path.read_text(encoding="utf-8")

    assert 'SEED_VERSION = "demo-learning-v1"' in source
    assert 'MISSIONS_PER_FACILITY = 50' in source
    assert "status = 'Completed'" in source
    assert "DELETE FROM optimization_action_effectiveness" in source
    assert "optimization_mission_actions" in source
    assert "optimization_missions" in source


def test_demo_learning_uses_multiple_action_signatures():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "seed_mission_learning_demo.py"
    )
    source = path.read_text(encoding="utf-8")

    for action in (
        "REASSIGN_DOCK",
        "PRE_STAGE_PRODUCTS",
        "ADD_LOADER",
        "PRIORITY_SEQUENCE",
        "ADD_FORKLIFT",
    ):
        assert action in source
