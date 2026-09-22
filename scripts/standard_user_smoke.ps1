$ErrorActionPreference = 'Stop'
$account = 'WanwanSmoke'
$base = Join-Path $env:PUBLIC ('WanwanSmoke-' + [guid]::NewGuid().ToString('N'))
$secret = [guid]::NewGuid().ToString('N') + 'aA1!'
$secure = ConvertTo-SecureString $secret -AsPlainText -Force
$rule = 'Wanwan smoke outbound block'
$originalTemp = $env:TEMP
$originalTmp = $env:TMP
$originalPath = $env:PATH
try {
    New-LocalUser -Name $account -Password $secure -Description 'Ephemeral release smoke test' | Out-Null
    $usersGroup = Get-LocalGroup -SID 'S-1-5-32-545'
    Add-LocalGroupMember -Group $usersGroup.Name -Member $account
    New-Item -ItemType Directory -Path $base | Out-Null
    New-Item -ItemType Directory -Path "$base/temp" | Out-Null
    Copy-Item dist/WanwanTeacherHelper.exe "$base/WanwanTeacherHelper.exe"
    & icacls $base /grant "${account}:(OI)(CI)M" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Failed to grant smoke output permission' }
    New-NetFirewallRule -DisplayName $rule -Direction Outbound -Program "$base/WanwanTeacherHelper.exe" -Action Block | Out-Null
    $env:TEMP = "$base/temp"
    $env:TMP = "$base/temp"
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $credential = [pscredential]::new("$env:COMPUTERNAME\$account", $secure)
    $p = Start-Process -FilePath "$base/WanwanTeacherHelper.exe" -ArgumentList '--self-test', "$base/results" -WorkingDirectory $base -Credential $credential -LoadUserProfile -PassThru
    if (!$p.WaitForExit(240000)) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        throw 'Standard user smoke timed out'
    }
    if ($p.ExitCode -ne 0) { throw "Standard user smoke failed: $($p.ExitCode)" }
    $report = Get-Content "$base/results/self-test.json" -Raw | ConvertFrom-Json
    if ($report.status -ne 'passed' -or $report.is_admin -ne $false) { throw 'Expected a passing non-admin smoke report' }
} finally {
    $env:TEMP = $originalTemp
    $env:TMP = $originalTmp
    $env:PATH = $originalPath
    New-Item -ItemType Directory -Force artifacts/standard-user-smoke | Out-Null
    if (Test-Path "$base/results") {
        Copy-Item "$base/results/*" artifacts/standard-user-smoke -Recurse -Force
    }
    Remove-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue
    Remove-LocalUser -Name $account -ErrorAction SilentlyContinue
    if (Test-Path $base) { Remove-Item $base -Recurse -Force -ErrorAction SilentlyContinue }
}
