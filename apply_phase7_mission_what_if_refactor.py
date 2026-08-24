from pathlib import Path

ROOT = Path(r"C:\turn-time-management")
TARGET = ROOT / "frontend" / "src" / "components" / "AiMissionCenter.tsx"
NEW_COMPONENT = ROOT / "frontend" / "src" / "components" / "MissionWhatIfPanel.tsx"
SOURCE_COMPONENT = Path(__file__).resolve().parent / "frontend" / "src" / "components" / "MissionWhatIfPanel.tsx"

text = TARGET.read_text(encoding="utf-8")

import_anchor = """import {
  acceptOptimizationMission,
  simulateOptimizationMission,
  refreshOptimizationMissionOutcomes,
  updateOptimizationMissionStatus,
} from "../services/optimization";
"""
if 'from "./MissionWhatIfPanel"' not in text:
    if import_anchor not in text:
        raise RuntimeError("Could not find optimization import anchor.")
    text = text.replace(
        import_anchor,
        import_anchor + 'import { MissionWhatIfPanel } from "./MissionWhatIfPanel";\n',
        1,
    )

start_marker = """                {scenarioMissionId === mission.mission_id &&
                  mission.category === "Coordinated Recovery" && (
                    <div className="mission-what-if-panel">"""
next_marker = """                {mission.effectiveStatus === "Completed" &&"""

start = text.find(start_marker)
if start == -1:
    raise RuntimeError("Could not find Mission What-If block start.")

next_start = text.find(next_marker, start)
if next_start == -1:
    raise RuntimeError("Could not find Completed mission block after What-If.")

replacement = """                {scenarioMissionId === mission.mission_id &&
                  mission.category === "Coordinated Recovery" && (
                    <MissionWhatIfPanel
                      mission={mission}
                      scenario={scenarioFor(mission)}
                      scenarioResult={scenarioResults[mission.mission_id]}
                      loading={scenarioLoadingId === mission.mission_id}
                      onUpdateScenario={(patch) =>
                        updateScenario(mission, patch)
                      }
                      onRunScenario={() => runMissionScenario(mission)}
                    />
                  )}


"""

text = text[:start] + replacement + text[next_start:]

NEW_COMPONENT.write_text(
    SOURCE_COMPONENT.read_text(encoding="utf-8"),
    encoding="utf-8",
)
TARGET.write_text(text, encoding="utf-8")

print("Phase 7 applied successfully.")
print(f"Updated: {TARGET}")
print(f"Added:   {NEW_COMPONENT}")
