# Copilot ranking reliability fix

Changes:
- Primary ranking requires at least 5 appointments when any group meets that threshold.
- Groups with 1–4 appointments remain visible and are labeled `Limited sample`.
- A higher raw value from a limited sample is explicitly called out but does not become the confident leader.
- If every group is below 5 appointments, Copilot answers with an explicit limited-evidence warning.
- Fixes singular/plural grammar (`1 appointment`, `2 appointments`).
- Adds regression tests for the Dock 01 vs Dock 07 scenario and all-small-sample behavior.

Apply the two backend files to the matching repository paths, then run:

    cd C:\turn-time-management\backend
    pytest

Restart FastAPI and retest:

    Which docks have the highest average risk today?
