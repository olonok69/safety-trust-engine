param(
    [string]$Repository,
    [string]$Branch = "main"
)

<#
.SYNOPSIS
  Temporarily relax main branch protection for fast WIP iteration.

.DESCRIPTION
  Drops merge-demo-pass and conversation-resolution requirements so PRs only
  need lint-and-test. Use while building features (e.g. US compliance packs)
  to avoid long green-merge demo cycles and noisy bot re-runs.

  Restore strict policy when done:
    ./.github/scripts/protect-main.ps1
#>

$ErrorActionPreference = "Stop"

function Get-RepositorySlug {
    param([string]$RemoteUrl)

    if ($RemoteUrl -match '^https://github\.com/(?<owner>[^/]+)/(?<repo>[^/]+?)(?:\.git)?/?$|^git@github\.com:(?<owner_ssh>[^/]+)/(?<repo_ssh>[^/]+?)(?:\.git)?$') {
        $owner = if ($Matches.owner) { $Matches.owner } else { $Matches.owner_ssh }
        $repo = if ($Matches.repo) { $Matches.repo } else { $Matches.repo_ssh }
        if (-not $owner -or -not $repo) {
            throw "Unable to infer repository slug from origin remote: $RemoteUrl"
        }
        return "$owner/$repo"
    }

    throw "Unable to infer repository slug from origin remote: $RemoteUrl"
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required. Install it first and make sure it is on PATH."
}

if (-not $Repository) {
    $remoteUrl = git remote get-url origin
    $Repository = Get-RepositorySlug -RemoteUrl $remoteUrl
}

if (-not $env:GH_TOKEN) {
    $status = & gh auth status 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "gh is not authenticated. Set GH_TOKEN in the environment or run 'gh auth login' first."
    }
}

$body = @{
    required_status_checks = @{
        strict = $true
        checks = @(
            @{ context = "lint-and-test" }
        )
    }
    enforce_admins = $true
    required_pull_request_reviews = @{
        dismiss_stale_reviews = $true
        require_code_owner_reviews = $false
        required_approving_review_count = 0
        require_last_push_approval = $false
    }
    allow_force_pushes = $false
    allow_deletions = $false
    required_linear_history = $false
    required_conversation_resolution = $false
    restrictions = $null
} | ConvertTo-Json -Depth 6

$uri = "repos/$Repository/branches/$Branch/protection"

Write-Host "Relaxing branch protection on $Repository/$Branch..."
Write-Host "  required checks: lint-and-test only (merge-demo-pass dropped)"
Write-Host "  conversation resolution: off"
$body | gh api -X PUT $uri --input -
Write-Host "Relaxed policy applied. Restore with: ./.github/scripts/protect-main.ps1"
