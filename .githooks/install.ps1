# Install local git hooks (strips bot Co-authored-by trailers).

# Run once per clone:
#   powershell -File .githooks/install.ps1

$ErrorActionPreference = "Stop"
$root = git rev-parse --show-toplevel
Set-Location $root
git config core.hooksPath .githooks
Write-Host "core.hooksPath -> .githooks"
Write-Host "prepare-commit-msg will strip Cursor/Claude/Copilot Co-authored-by trailers."
