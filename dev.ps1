# Windows PowerShell 5.1+. Run from the repository with .\dev.ps1.
[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$BackendPort = 8000,
    [ValidateRange(1024, 65535)][int]$FrontendPort = 3000
)

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$children = New-Object 'System.Collections.Generic.List[System.Diagnostics.Process]'
$ownedProcesses = @{}

function Read-BackendConfiguration {
    $settings = @{}
    $dotenv = Join-Path $repoRoot '.env'
    if (Test-Path -LiteralPath $dotenv) {
        foreach ($line in [IO.File]::ReadAllLines($dotenv)) {
            if ($line -match '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
                $name, $value = $Matches[1], $Matches[2]
                if ($name -notmatch '^(GEMINI_(API_KEY_FILE|API_KEY|MODEL)|WEB_[A-Z_]+)$') { continue }
                if ($value.Length -ge 2 -and (($value[0] -eq '"' -and $value[-1] -eq '"') -or
                    ($value[0] -eq "'" -and $value[-1] -eq "'"))) {
                    $value = $value.Substring(1, $value.Length - 2)
                } else { $value = ($value -split '\s+#', 2)[0].Trim() }
                $settings[$name] = $value
            }
        }
    }
    # Process environment wins; .env is parsed as data, never executed.
    foreach ($entry in [Environment]::GetEnvironmentVariables().GetEnumerator()) {
        if ($entry.Key -match '^(GEMINI_(API_KEY_FILE|API_KEY|MODEL)|WEB_[A-Z_]+)$' -and $entry.Value) {
            $settings[$entry.Key] = [string]$entry.Value
        }
    }
    if (-not $settings['GEMINI_API_KEY_FILE'] -and
        $settings['GEMINI_API_KEY'] -notmatch '^AIza[0-9A-Za-z_-]{35}$') {
        $settings['GEMINI_API_KEY_FILE'] = 'src/api/api_key/api_gemini.txt'
    }
    if ($settings['GEMINI_API_KEY_FILE']) {
        $keyPath = $settings['GEMINI_API_KEY_FILE']
        if (-not [IO.Path]::IsPathRooted($keyPath)) { $keyPath = Join-Path $repoRoot $keyPath }
        if (-not (Test-Path -LiteralPath $keyPath -PathType Leaf)) {
            throw 'Gemini key file not found. Check GEMINI_API_KEY_FILE in .env; keys are never printed.'
        }
        if ((Get-Item -LiteralPath $keyPath).Length -gt 1MB) { throw 'Gemini key file exceeds 1 MiB.' }
        $keyText = [IO.File]::ReadAllText($keyPath)
        $settings['GEMINI_API_KEY_FILE'] = [IO.Path]::GetFullPath($keyPath)
    } else { $keyText = $settings['GEMINI_API_KEY'] }
    if ($keyText -notmatch '(?m)^\s*AIza[0-9A-Za-z_-]{35}\s*$') {
        throw 'No valid Gemini key found in local configuration. No keys were sent or printed.'
    }
    $origins = @($settings['WEB_ALLOWED_ORIGINS'] -split ',' | Where-Object { $_ })
    $origins += "http://127.0.0.1:$FrontendPort", "http://localhost:$FrontendPort"
    $settings['WEB_ALLOWED_ORIGINS'] = ($origins | Select-Object -Unique) -join ','
    return $settings
}

function Assert-FreePort([int]$Port) {
    $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, $Port)
    try { $listener.Start() }
    catch { throw "Port $Port is already in use. No existing process was stopped." }
    finally { $listener.Stop() }
}

function Start-DevProcess([string]$Executable, [string[]]$StartupArguments,
                          [string]$Directory, [hashtable]$Settings, [bool]$Frontend = $false) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Executable
    # Arguments are generated locally; Windows filenames cannot contain double quotes.
    $info.Arguments = ($StartupArguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
    $info.WorkingDirectory = $Directory
    $info.UseShellExecute = $false
    # Inherit this console so Ctrl+C reaches both servers. No additional windows.
    $info.CreateNoWindow = $false
    foreach ($name in $Settings.Keys) { $info.EnvironmentVariables[$name] = $Settings[$name] }
    if ($Frontend) {
        # Backend secrets from the parent shell are unnecessary in Next.js.
        foreach ($name in @($info.EnvironmentVariables.Keys)) {
            if ($name -match '^GEMINI_|^WEB_GEMINI_') { $info.EnvironmentVariables.Remove($name) }
        }
        $info.EnvironmentVariables['BACKEND_URL'] = "http://127.0.0.1:$BackendPort"
    }
    $child = New-Object Diagnostics.Process
    $child.StartInfo = $info
    if (-not $child.Start()) { throw 'Could not start development server.' }
    $children.Add($child)
    $ownedProcesses[$child.Id] = $child.StartTime.Ticks
    return $child
}

function Update-OwnedProcesses {
    $queue = New-Object 'System.Collections.Generic.Queue[int]'
    foreach ($idValue in @($ownedProcesses.Keys)) { $queue.Enqueue($idValue) }
    while ($queue.Count) {
        $parentId = $queue.Dequeue()
        try { $parent = [Diagnostics.Process]::GetProcessById($parentId) } catch { continue }
        if ($parent.StartTime.Ticks -ne $ownedProcesses[$parentId]) { continue }
        foreach ($item in @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $parentId")) {
            $childId = [int]$item.ProcessId
            if (-not $ownedProcesses.ContainsKey($childId)) {
                try {
                    $ownedProcesses[$childId] = [Diagnostics.Process]::GetProcessById($childId).StartTime.Ticks
                    $queue.Enqueue($childId)
                } catch { } # Process may have exited during the snapshot.
            }
        }
    }
}

function Stop-DevProcesses {
    try { Update-OwnedProcesses } catch { }
    # Allow SIGINT handlers to finish before falling back to owned process trees.
    $deadline = [DateTime]::UtcNow.AddSeconds(3)
    foreach ($child in $children) {
        $remaining = [Math]::Max(0, [int]($deadline - [DateTime]::UtcNow).TotalMilliseconds)
        if (-not $child.HasExited) { $null = $child.WaitForExit($remaining) }
    }
    foreach ($idValue in @($ownedProcesses.Keys)) {
        try {
            $live = [Diagnostics.Process]::GetProcessById($idValue)
            if ($live.StartTime.Ticks -ne $ownedProcesses[$idValue]) { continue }
            $info = New-Object Diagnostics.ProcessStartInfo
            $info.FileName = Join-Path $env:SystemRoot 'System32/taskkill.exe'
            $info.Arguments = "/PID $idValue /T /F"
            $info.UseShellExecute, $info.CreateNoWindow = $false, $true
            $info.RedirectStandardOutput, $info.RedirectStandardError = $true, $true
            $killer = [Diagnostics.Process]::Start($info)
            $null = $killer.WaitForExit(3000)
            $killer.Dispose()
        } catch { } # Already exited, or PID was recycled; never kill by name/port.
    }
    foreach ($child in $children) { $child.Dispose() }
}

Push-Location -LiteralPath $repoRoot
try {
    if ($env:OS -ne 'Windows_NT') { throw 'This launcher requires Windows PowerShell.' }
    if ($BackendPort -eq $FrontendPort) { throw 'Backend and frontend ports must differ.' }
    $python = Join-Path $repoRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Create .venv first: py -3.12 -m venv .venv; then .venv\Scripts\python.exe -m pip install -e ".[dev]"'
    }
    & $python -c "import sys; assert sys.version_info >= (3,11); import uvicorn; import vietnamese_financial_multi_agent.api.main"
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependencies missing. Run .venv\Scripts\python.exe -m pip install -e ".[dev]"' }
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    & $node -e "if(Number(process.versions.node.split('.')[0])<24)process.exit(1)"
    if ($LASTEXITCODE -ne 0) { throw 'Node.js 24 or newer is required.' }
    $webRoot = Join-Path $repoRoot 'web'
    $next = Join-Path $webRoot 'node_modules/next/dist/bin/next'
    if (-not (Test-Path -LiteralPath $next)) { throw 'Frontend dependencies missing. Run npm.cmd ci in web/.' }
    $settings = Read-BackendConfiguration
    Assert-FreePort $BackendPort
    Assert-FreePort $FrontendPort
    $backend = Start-DevProcess $python @('-m', 'uvicorn', 'vietnamese_financial_multi_agent.api.main:app',
        '--host', '127.0.0.1', '--port', [string]$BackendPort) $repoRoot $settings
    $frontendSettings = @{}
    if ($settings['WEB_MAX_UPLOAD_BYTES']) { $frontendSettings['WEB_MAX_UPLOAD_BYTES'] = $settings['WEB_MAX_UPLOAD_BYTES'] }
    $frontend = Start-DevProcess $node @($next, 'dev', '--hostname', '127.0.0.1', '--port', [string]$FrontendPort) $webRoot $frontendSettings $true
    Write-Host "Web: http://127.0.0.1:$FrontendPort"
    Write-Host "API: http://127.0.0.1:$BackendPort/api/health"
    Write-Host 'Gemini keys: configured locally (backend only). Press Ctrl+C to stop both servers.'
    while ($true) {
        Update-OwnedProcesses
        if ($backend.HasExited -or $frontend.HasExited) { throw 'A development server exited; stopping the other server.' }
        Start-Sleep -Milliseconds 500
    }
} finally {
    Stop-DevProcesses
    Pop-Location
    if ($children.Count) { Write-Host 'Development servers stopped.' }
}
