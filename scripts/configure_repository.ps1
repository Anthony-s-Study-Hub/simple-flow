param(
    [string]$Repo = "Anthony-s-Study-Hub/simple-flow",
    [string]$Branch = "main",
    [string]$GhPath = "C:\Program Files\GitHub CLI\gh.exe"
)

& $GhPath api "repos/$Repo" `
  --method PATCH `
  --field delete_branch_on_merge=true `
  --field allow_auto_merge=false

$body = @{
    required_status_checks = @{
        strict = $true
        contexts = @("phase1-gates", "phase1-tests")
    }
    enforce_admins = $true
    required_pull_request_reviews = @{
        dismiss_stale_reviews = $false
        require_code_owner_reviews = $false
        required_approving_review_count = 0
        require_last_push_approval = $false
    }
    restrictions = $null
    required_conversation_resolution = $true
    allow_force_pushes = $false
    allow_deletions = $false
} | ConvertTo-Json -Depth 10

$tempFile = New-TemporaryFile
try {
    Set-Content -LiteralPath $tempFile -Value $body -Encoding UTF8
    & $GhPath api "repos/$Repo/branches/$Branch/protection" `
      --method PUT `
      --input $tempFile
}
finally {
    Remove-Item -LiteralPath $tempFile -Force
}

Write-Output "Repository settings and '$Branch' branch protection updated."
