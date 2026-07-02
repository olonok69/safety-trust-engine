param(
    [string]$Repository,
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

function Get-RepositorySlug {
    param(
        [string]$RemoteUrl
    )

    if ($RemoteUrl -match 'github\.com[:/](?<owner>[^/]+)/(?<repo>[^/.]+)') {
        return "$($Matches.owner)/$($Matches.repo)"
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
            @{ context = "lint-and-test" },
            @{ context = "demo-gate" },
            @{ context = "safety-gate" }
        )
    }
    enforce_admins = $true
    required_pull_request_reviews = @{
        dismiss_stale_reviews = $true
        require_code_owner_reviews = $false
        required_approving_review_count = 1
        require_last_push_approval = $false
    }
    allow_force_pushes = $false
    allow_deletions = $false
    required_linear_history = $false
    required_conversation_resolution = $true
    restrictions = $null
} | ConvertTo-Json -Depth 6

$uri = "repos/$Repository/branches/$Branch/protection"

Write-Host "Applying branch protection to $Repository/$Branch..."
$body | gh api -X PUT $uri --input -
Write-Host "Branch protection applied. Direct pushes to $Branch are now blocked by GitHub rules."