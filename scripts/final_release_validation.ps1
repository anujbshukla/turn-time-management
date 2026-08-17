param(
    [string]$BackendUrl = "http://127.0.0.1:8000",
    [string]$FrontendUrl = "http://localhost:5173",
    [string]$FacilityId = "FAC001",
    [switch]$SkipFrontendHttp
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Invoke-JsonGet {
    param([string]$Url)
    return Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 60
}

Write-Host "Turn Time Management - Final Release Validation" -ForegroundColor Green
Write-Host "Project: $ProjectRoot"
Write-Host "Backend: $BackendUrl"
Write-Host "Frontend: $FrontendUrl"
Write-Host "Facility: $FacilityId"

# ------------------------------------------------------------
# 1. Git safety
# ------------------------------------------------------------
Write-Step "Checking Git working tree"
Push-Location $ProjectRoot
try {
    $branch = (git branch --show-current).Trim()
    $status = git status --porcelain

    Write-Host "Branch: $branch"

    Assert-True (
        $branch -eq "feature/ml-v2-optimization"
    ) "Expected feature/ml-v2-optimization before release validation; current branch is '$branch'."

    if ($status) {
        Write-Host "Working tree contains changes. This is expected before the final commit:" -ForegroundColor Yellow
        git status --short
    } else {
        Write-Host "Working tree clean."
    }
}
finally {
    Pop-Location
}

# ------------------------------------------------------------
# 2. Backend automated tests
# ------------------------------------------------------------
Write-Step "Running full backend pytest suite"
Push-Location (Join-Path $ProjectRoot "backend")
try {
    python -m pytest
    Assert-True ($LASTEXITCODE -eq 0) "Backend pytest failed."
}
finally {
    Pop-Location
}

# ------------------------------------------------------------
# 3. Database migration head
# ------------------------------------------------------------
Write-Step "Checking Alembic migration head"
Push-Location (Join-Path $ProjectRoot "backend")
try {
    $heads = (alembic heads | Out-String).Trim()
    $current = (alembic current | Out-String).Trim()

    Write-Host $heads
    Write-Host $current

    Assert-True (
        $heads -match "h5f2c8a7d630"
    ) "Expected Alembic head h5f2c8a7d630."

    Assert-True (
        $current -match "h5f2c8a7d630"
    ) "Database is not at h5f2c8a7d630."
}
finally {
    Pop-Location
}

# ------------------------------------------------------------
# 4. Frontend compile + production bundle
# ------------------------------------------------------------
Write-Step "Running frontend production build"
Push-Location (Join-Path $ProjectRoot "frontend")
try {
    npm run build
    Assert-True ($LASTEXITCODE -eq 0) "Frontend production build failed."
}
finally {
    Pop-Location
}

# ------------------------------------------------------------
# 5. Basic backend health
# ------------------------------------------------------------
Write-Step "Checking backend health"
$health = Invoke-JsonGet "$BackendUrl/health"
Assert-True ($health.status -eq "healthy") "Backend /health did not report healthy."
Write-Host "Backend health: healthy"

# ------------------------------------------------------------
# 6. Release readiness
# ------------------------------------------------------------
Write-Step "Checking release readiness"
$readiness = Invoke-JsonGet "$BackendUrl/health/readiness"

Assert-True ($readiness.ready -eq $true) (
    "Readiness check failed: " +
    ($readiness | ConvertTo-Json -Depth 8)
)

foreach ($property in $readiness.checks.PSObject.Properties) {
    $check = $property.Value
    Write-Host ("{0}: {1} - {2}" -f $property.Name, $check.status, $check.message)
    Assert-True (
        $check.status -eq "ready"
    ) "Readiness dependency '$($property.Name)' is not ready."
}

# ------------------------------------------------------------
# 7. Appointment API smoke
# ------------------------------------------------------------
Write-Step "Checking appointment queue"
$facility = [uri]::EscapeDataString($FacilityId)
$appointments = Invoke-JsonGet (
    "$BackendUrl/api/appointments/paged?page=1&page_size=10&facility_id=$facility"
)

# Different revisions have used items/data for paged payloads; tolerate either.
$items = $null
if ($appointments.PSObject.Properties.Name -contains "items") {
    $items = @($appointments.items)
}
elseif ($appointments.PSObject.Properties.Name -contains "data") {
    $items = @($appointments.data)
}
else {
    throw "Appointment paging response does not contain items or data."
}

Assert-True ($items.Count -gt 0) "Appointment API returned no rows for $FacilityId."
$appointmentId = [string]$items[0].appt_id
Assert-True (-not [string]::IsNullOrWhiteSpace($appointmentId)) "Appointment response is missing appt_id."
Write-Host "Sample appointment: $appointmentId"

$details = Invoke-JsonGet (
    "$BackendUrl/api/appointments/$([uri]::EscapeDataString($appointmentId))/details"
)
Assert-True ($details -ne $null) "Appointment details endpoint returned no payload."

# ------------------------------------------------------------
# 8. ML production status + registry
# ------------------------------------------------------------
Write-Step "Checking ML model status and registry"
$mlStatus = Invoke-JsonGet "$BackendUrl/api/ml/status"
Write-Host ($mlStatus | ConvertTo-Json -Depth 4)

$registry = @(Invoke-JsonGet "$BackendUrl/api/ml/registry?limit=20")
Assert-True ($registry.Count -gt 0) "ML model registry is empty."

$productionModels = @(
    $registry | Where-Object { $_.status -eq "Production" }
)
Assert-True (
    $productionModels.Count -eq 1
) "Expected exactly one Production model in the registry."

Write-Host "Production model: $($productionModels[0].model_version)"

# ------------------------------------------------------------
# 9. ML monitoring / governance
# ------------------------------------------------------------
Write-Step "Checking ML monitoring"
$monitoring = Invoke-JsonGet (
    "$BackendUrl/api/ml/monitoring?window_days=30&persist=false&facility_id=$facility"
)

Assert-True (
    @("Healthy", "Watch", "Retrain Recommended") -contains $monitoring.health_status
) "Unexpected ML governance status '$($monitoring.health_status)'."

Write-Host "Model health: $($monitoring.health_status)"
Write-Host "Feature drift: $($monitoring.feature_drift.score)"
Write-Host "Realized prediction sample: $($monitoring.performance.sample_size)"

# Watch is acceptable for a demo environment with insufficient realized production outcomes.
if ($monitoring.health_status -eq "Retrain Recommended") {
    Write-Host "WARNING: Governance currently recommends retraining." -ForegroundColor Yellow
    Write-Host ($monitoring.reasons -join "`n")
}

# ------------------------------------------------------------
# 10. Read-only multi-appointment optimization preview
# ------------------------------------------------------------
Write-Step "Checking coordinated recovery optimizer preview"
$today = Get-Date
$dateFrom = $today.ToString("yyyy-MM-dd")
$dateTo = $today.AddDays(1).ToString("yyyy-MM-dd")

$optimizerBody = @{
    facility_id = $FacilityId
    date_from = $dateFrom
    date_to = $dateTo
    max_missions = 3
} | ConvertTo-Json

$optimizer = Invoke-RestMethod `
    -Method Post `
    -Uri "$BackendUrl/api/optimization/preview" `
    -ContentType "application/json" `
    -Body $optimizerBody `
    -TimeoutSec 120

Assert-True (
    $optimizer.PSObject.Properties.Name -contains "missions"
) "Optimization preview response is missing missions."

Write-Host "Candidate appointments: $($optimizer.candidate_appointments)"
Write-Host "Generated missions: $(@($optimizer.missions).Count)"

# ------------------------------------------------------------
# 11. Mission-level What-If scenario
# ------------------------------------------------------------
Write-Step "Checking mission-level What-If"
$scenarioBody = @{
    facility_id = $FacilityId
    date_from = $dateFrom
    date_to = $dateTo
    max_missions = 1
    max_extra_loaders_per_hour = 1
    max_extra_forklifts_per_hour = 1
    max_staging_labor_per_hour = 1
    allow_dock_reassignment = $true
} | ConvertTo-Json

$scenario = Invoke-RestMethod `
    -Method Post `
    -Uri "$BackendUrl/api/optimization/scenario" `
    -ContentType "application/json" `
    -Body $scenarioBody `
    -TimeoutSec 120

Assert-True (
    $scenario.PSObject.Properties.Name -contains "scenario_constraints"
) "Mission-level What-If response is missing scenario_constraints."

Write-Host "Scenario missions: $(@($scenario.missions).Count)"

# ------------------------------------------------------------
# 12. Action effectiveness learning endpoint
# ------------------------------------------------------------
Write-Step "Checking action-effectiveness learning"
$effectiveness = @(
    Invoke-JsonGet (
        "$BackendUrl/api/optimization/learning/action-effectiveness?facility_id=$facility&limit=20"
    )
)
Write-Host "Learned effectiveness profiles: $($effectiveness.Count)"
# Zero is valid before enough executed missions accumulate.

# ------------------------------------------------------------
# 13. Optional frontend HTTP smoke
# ------------------------------------------------------------
if (-not $SkipFrontendHttp) {
    Write-Step "Checking running frontend"
    try {
        $frontendResponse = Invoke-WebRequest `
            -Uri $FrontendUrl `
            -Method Get `
            -TimeoutSec 15 `
            -UseBasicParsing
        Assert-True (
            $frontendResponse.StatusCode -ge 200 -and
            $frontendResponse.StatusCode -lt 400
        ) "Frontend HTTP status is $($frontendResponse.StatusCode)."
        Write-Host "Frontend HTTP status: $($frontendResponse.StatusCode)"
    }
    catch {
        throw (
            "Frontend smoke check failed. Start Vite first or run this script " +
            "with -SkipFrontendHttp. Details: $($_.Exception.Message)"
        )
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "FINAL RELEASE VALIDATION PASSED" -ForegroundColor Green
Write-Host "Branch: $branch" -ForegroundColor Green
Write-Host "Alembic: h5f2c8a7d630" -ForegroundColor Green
Write-Host "Backend tests: PASS" -ForegroundColor Green
Write-Host "Frontend build: PASS" -ForegroundColor Green
Write-Host "Runtime readiness: PASS" -ForegroundColor Green
Write-Host "Appointments / ML / optimizer / What-If APIs: PASS" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
