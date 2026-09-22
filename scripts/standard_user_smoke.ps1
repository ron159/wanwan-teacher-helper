$ErrorActionPreference = 'Stop'
$account = 'WanwanSmoke'
$base = Join-Path $env:PUBLIC ('WanwanSmoke-' + [guid]::NewGuid().ToString('N'))
$secret = [guid]::NewGuid().ToString('N') + 'aA1!'
$secure = ConvertTo-SecureString $secret -AsPlainText -Force
$rule = 'Wanwan offline acceptance ' + [guid]::NewGuid().ToString('N')
$watchdog = 'Wanwan-network-recovery'
$executable = Join-Path $base 'WanwanTeacherHelper.exe'
$savedEnvironment = @{}
foreach ($key in @('TEMP', 'TMP', 'PATH', 'LOCALAPPDATA')) { $savedEnvironment[$key] = [Environment]::GetEnvironmentVariable($key) }
$profiles = Get-NetFirewallProfile | Select-Object Name, Enabled

function Test-ExternalConnection([string] $address) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $pending = $client.BeginConnect($address, 443, $null, $null)
        if (!$pending.AsyncWaitHandle.WaitOne(2000)) { return $false }
        $client.EndConnect($pending)
        return $client.Connected
    } catch { return $false } finally { $client.Dispose() }
}

function Invoke-UserProbe([string] $mode, [string] $folder) {
    $start = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
    $p = Start-Process -FilePath $executable -ArgumentList $mode, $folder -WorkingDirectory $base -Credential $credential -LoadUserProfile -PassThru
    if (!$p.WaitForExit(120000)) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        throw 'Standard user probe timed out'
    }
    if ($p.ExitCode -ne 0) { throw "Standard user probe failed: $($p.ExitCode)" }
    return $start
}

try {
    New-LocalUser -Name $account -Password $secure -Description 'Ephemeral release acceptance' | Out-Null
    $usersGroup = Get-LocalGroup -SID 'S-1-5-32-545'
    Add-LocalGroupMember -Group $usersGroup.Name -Member $account
    New-Item -ItemType Directory -Path $base | Out-Null
    foreach ($folder in @('temp', 'localappdata')) { New-Item -ItemType Directory -Path (Join-Path $base $folder) | Out-Null }
    Copy-Item dist/WanwanTeacherHelper.exe $executable
    & icacls $base /grant "${account}:(OI)(CI)M" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Failed to grant smoke output permission' }
    $address = (Resolve-DnsName api.github.com -Type A | Where-Object IPAddress | Select-Object -First 1).IPAddress
    if (!(Test-ExternalConnection $address)) { throw 'Cannot establish online baseline for offline test' }

    # Recover connectivity even if the acceptance process is terminated unexpectedly.
    $restore = Join-Path $base 'restore-network.ps1'
    $restoreLines = @("Remove-NetFirewallRule -DisplayName '$rule' -ErrorAction SilentlyContinue")
    foreach ($profile in $profiles) { $restoreLines += "Set-NetFirewallProfile -Name '$($profile.Name)' -Enabled $($profile.Enabled)" }
    $restoreLines | Set-Content $restore
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$restore`""
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5)
    Register-ScheduledTask -TaskName $watchdog -Action $action -Trigger $trigger -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
    Set-NetFirewallProfile -Profile Domain, Private, Public -Enabled True
    # Blocks every process, including extracted FFmpeg/ffprobe, on this ephemeral runner.
    New-NetFirewallRule -DisplayName $rule -Direction Outbound -Action Block -Profile Any | Out-Null
    if (Test-ExternalConnection $address) { throw 'Outbound connection unexpectedly succeeded while blocked' }
    $env:TEMP = Join-Path $base 'temp'
    $env:TMP = $env:TEMP
    $env:LOCALAPPDATA = Join-Path $base 'localappdata'
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $credential = [pscredential]::new("$env:COMPUTERNAME\$account", $secure)
    $probeFolder = Join-Path $base 'startup'
    $launch = Invoke-UserProbe '--startup-probe' $probeFolder
    $startup = Get-Content (Join-Path $probeFolder 'startup-probe.json') -Raw | ConvertFrom-Json
    if (!$startup.frozen -or $startup.is_admin) { throw 'Invalid ordinary-user frozen startup report' }
    $resultsFolder = Join-Path $base 'results'
    $null = Invoke-UserProbe '--self-test' $resultsFolder
    $report = Get-Content (Join-Path $resultsFolder 'self-test.json') -Raw | ConvertFrom-Json
    if ($report.status -ne 'passed' -or $report.is_admin -ne $false) { throw 'Expected passing non-admin acceptance' }
    if (Test-ExternalConnection $address) { throw 'Network block was lost during acceptance' }
    $cacheBytes = (Get-ChildItem $env:LOCALAPPDATA -File -Recurse | Measure-Object Length -Sum).Sum
    $remainingExtraction = @(Get-ChildItem $env:TEMP -Directory -Filter '_MEI*').Count
    if ($remainingExtraction -ne 0) { throw 'Onefile extraction directory was not cleaned' }
    @{
        all_processes_outbound_blocked = $true
        online_probe_succeeded_before_block = $true
        offline_probe_failed_during_block = $true
        launch_to_ui_ready_seconds = [math]::Round($startup.ui_ready_unix - $launch, 3)
        extracted_bundle_bytes = $startup.bundle_bytes
        engine_cache_bytes = $cacheBytes
        temporary_extraction_cleaned = $true
        admin = $false
        cases = $report.cases
    } | ConvertTo-Json | Set-Content (Join-Path $resultsFolder 'deployment-acceptance.json')
} finally {
    # Restore runner connectivity before uploading artifacts or cleanup.
    Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
    foreach ($profile in $profiles) { Set-NetFirewallProfile -Name $profile.Name -Enabled $profile.Enabled }
    Unregister-ScheduledTask -TaskName $watchdog -Confirm:$false -ErrorAction SilentlyContinue
    foreach ($key in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($key, $savedEnvironment[$key]) }
    New-Item -ItemType Directory -Force artifacts/standard-user-smoke | Out-Null
    if (Test-Path (Join-Path $base 'results')) { Copy-Item "$base/results/*" artifacts/standard-user-smoke -Recurse -Force }
    if (Test-Path (Join-Path $base 'startup')) { Copy-Item "$base/startup/*" artifacts/standard-user-smoke -Force }
    Remove-LocalUser -Name $account -ErrorAction SilentlyContinue
    if (Test-Path $base) { Remove-Item $base -Recurse -Force -ErrorAction SilentlyContinue }
}
