# ============================================================
# Warehouse Copilot - NL V2 Coverage Batch Runner
# ============================================================

$ErrorActionPreference = "Continue"

# Change this if you want a longer/shorter delay between families.
$PauseSeconds = 60

# Enable live semantic-provider tests.
$env:RUN_COPILOT_NL_LIVE_TESTS = "true"

$TestFile = "tests/test_copilot_nl_v2_full_coverage_matrix.py"

$Families = @(
    @{
        Name = "Core metrics and rankings"
        Test = "test_core_metric_intent_grouping"
    },
    @{
        Name = "Temporal language"
        Test = "test_temporal_language"
    },
    @{
        Name = "Canonical dimension filters"
        Test = "test_canonical_dimension_filters"
    },
    @{
        Name = "Numeric filters"
        Test = "test_numeric_filter_semantics"
    },
    @{
        Name = "Specialized analytics"
        Test = "test_specialized_analytics_semantics"
    },
    @{
        Name = "Specialized intents"
        Test = "test_specialized_intents"
    },
    @{
        Name = "Multi-turn conversation state"
        Test = "test_follow_up_chain_preserves_and_mutates_state"
    },
    @{
        Name = "Dashboard date precedence"
        Test = "test_dashboard_date_is_not_used_when_user_specifies_time"
    }
)

$Passed = 0
$Failed = 0
$StartTime = Get-Date

Write-Host ""
Write-Host "=============================================="
Write-Host " Warehouse Copilot NL Coverage Batch Runner"
Write-Host "=============================================="
Write-Host "Families: $($Families.Count)"
Write-Host "Pause:    $PauseSeconds seconds"
Write-Host ""

for ($i = 0; $i -lt $Families.Count; $i++) {

    $Family = $Families[$i]

    Write-Host ""
    Write-Host "=============================================="
    Write-Host "[$($i + 1)/$($Families.Count)] $($Family.Name)"
    Write-Host "=============================================="
    Write-Host ""

    python -m pytest `
        "$TestFile::$($Family.Test)" `
        -vv -s

    $ExitCode = $LASTEXITCODE

    if ($ExitCode -eq 0) {

        $Passed++

        Write-Host ""
        Write-Host "PASSED: $($Family.Name)"

    }
    else {

        $Failed++

        Write-Host ""
        Write-Host "FAILED: $($Family.Name)"
        Write-Host "pytest exit code: $ExitCode"
        Write-Host ""
        Write-Host "Stopping the batch runner."
        Write-Host ""
        Write-Host "This prevents additional Gemini calls after a"
        Write-Host "semantic failure or provider/quota failure."
        break
    }

    # Don't pause after the final family.
    if ($i -lt ($Families.Count - 1)) {

        Write-Host ""
        Write-Host "Waiting $PauseSeconds seconds before next family..."

        for ($remaining = $PauseSeconds; $remaining -gt 0; $remaining--) {

            Write-Host -NoNewline "`rNext family in $remaining seconds... "

            Start-Sleep -Seconds 1
        }

        Write-Host "`rStarting next family...                  "
    }
}

$Duration = (Get-Date) - $StartTime

Write-Host ""
Write-Host "=============================================="
Write-Host " Batch Summary"
Write-Host "=============================================="
Write-Host "Passed families: $Passed"
Write-Host "Failed families: $Failed"
Write-Host "Elapsed: $([math]::Round($Duration.TotalMinutes, 1)) minutes"
Write-Host ""

if ($Failed -eq 0 -and $Passed -eq $Families.Count) {

    Write-Host "ALL NL COVERAGE FAMILIES PASSED."
    exit 0

}
else {

    Write-Host "NL COVERAGE VALIDATION INCOMPLETE."
    exit 1
}