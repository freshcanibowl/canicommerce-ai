# Read-only GitHub Actions pre-run failure diagnostics. No reruns or settings changes.
$ErrorActionPreference = "Stop"
$repo = "freshcanibowl/canicommerce-ai"
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) not installed"
}
gh auth status
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI authentication required" }
$runIds = @(38357962917, 38357962974)
foreach ($runId in $runIds) {
    Write-Host "Inspecting run $runId" -ForegroundColor Cyan
    $jobsJson = gh api "repos/$repo/actions/runs/$runId/jobs"
    if ($LASTEXITCODE -ne 0) { throw "Unable to read run jobs" }
    $jobs = ($jobsJson | ConvertFrom-Json).jobs
    foreach ($job in $jobs) {
        Write-Host "Job: $($job.name); runner: $($job.runner_name); steps: $(@($job.steps).Count)"
        $checkId = $job.id
        try {
            $annotations = gh api "repos/$repo/check-runs/$checkId/annotations" | ConvertFrom-Json
            foreach ($a in $annotations) {
                Write-Host "[$($a.annotation_level)] $($a.title): $($a.message)"
            }
        } catch {
            Write-Warning "Annotations unavailable for job $checkId"
        }
    }
}
Write-Host "Read-only diagnosis complete. Do not post tokens or secrets."
