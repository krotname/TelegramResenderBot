param(
    [string]$Repository = "krotname/Bot-Telegram-Resender",
    [string[]]$Branches = @("main", "master")
)

$protectionConfig = @{
    enforce_admins = $true
    required_status_checks = @{
        strict   = $true
        contexts = @(
            "lint (3.12)",
            "lint (3.13)",
            "types (3.12)",
            "types (3.13)",
            "tests (3.12)",
            "tests (3.13)",
            "security",
            "Analyze (python)"
        )
    }
    required_pull_request_reviews = @{
        dismiss_stale_reviews      = $true
        require_code_owner_reviews = $true
        require_last_push_approval = $true
        required_approving_review_count = 1
    }
    restrictions = $null
    required_linear_history = $true
    allow_force_pushes = $false
    allow_deletions = $false
    block_creations = $false
    required_conversation_resolution = $true
    lock_branch = $false
    allow_fork_syncing = $true
}

$json = $protectionConfig | ConvertTo-Json -Depth 20

foreach ($branch in $Branches) {
    & gh api "repos/$Repository/branches/$branch" --silent > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Output "Skipping '$branch': branch not found."
        continue
    }

    Write-Output "Applying protection to '$branch'..."
    $json | gh api --method PUT "repos/$Repository/branches/$branch/protection" `
        -H "Accept: application/vnd.github.luke-cage-preview+json" `
        --input - `
        | Out-Null
}

Write-Output "Done."
