param(
    [string]$Path = 'dist/WanwanTeacherHelper.exe',
    [string]$Report = 'artifacts/signature.json'
)
$ErrorActionPreference = 'Stop'
# Use an existing CA-issued signing identity. Never create/import a trust root.
$thumbprint = $env:WANWAN_SIGNING_THUMBPRINT
if ($thumbprint -notmatch '^[0-9A-Fa-f]{40}$') { throw 'Configure the expected production certificate thumbprint' }
$timestamp = $env:WANWAN_TIMESTAMP_URL
if (!$timestamp -or ![Uri]::IsWellFormedUriString($timestamp, [UriKind]::Absolute) -or !($timestamp -match '^https?://')) {
    throw 'Configure an RFC 3161 timestamp endpoint'
}
$tool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" |
    Sort-Object FullName -Descending | Select-Object -First 1
if (!$tool) { throw 'Windows SDK SignTool is required' }
$imported = $null
$pfx = $null
$existingCertificates = @(Get-ChildItem Cert:\CurrentUser\My | ForEach-Object Thumbprint)
try {
    if ($env:WANWAN_SIGNING_PFX_BASE64) {
        if (Test-Path "Cert:\CurrentUser\My\$thumbprint") { throw 'Refusing to replace an existing signing identity' }
        $pfx = Join-Path $env:RUNNER_TEMP ([Guid]::NewGuid().ToString() + '.pfx')
        [IO.File]::WriteAllBytes($pfx, [Convert]::FromBase64String($env:WANWAN_SIGNING_PFX_BASE64))
        $password = ConvertTo-SecureString $env:WANWAN_SIGNING_PFX_PASSWORD -AsPlainText -Force
        $imported = @(Import-PfxCertificate -FilePath $pfx -CertStoreLocation Cert:\CurrentUser\My -Password $password)
    }
    $certificate = Get-Item "Cert:\CurrentUser\My\$thumbprint"
    if (!$certificate.HasPrivateKey -or $certificate.Subject -eq $certificate.Issuer) { throw 'A non-self-signed certificate with private key is required' }
    if ($certificate.NotAfter -le (Get-Date) -or $certificate.NotBefore -gt (Get-Date)) { throw 'Signing certificate is not currently valid' }
    if ('1.3.6.1.5.5.7.3.3' -notin $certificate.EnhancedKeyUsageList.ObjectId.Value) { throw 'Certificate must allow code signing' }
    & $tool.FullName sign /sha1 $thumbprint /s My /fd SHA256 /tr $timestamp /td SHA256 $Path
    if ($LASTEXITCODE -ne 0) { throw 'Signing failed' }
    & $tool.FullName verify /pa /all /v $Path
    if ($LASTEXITCODE -ne 0) { throw 'Authenticode trust verification failed' }
    $signature = Get-AuthenticodeSignature $Path
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $thumbprint -or !$signature.TimeStamperCertificate) {
        throw 'Expected trusted signer and timestamp are required'
    }
    New-Item -ItemType Directory -Force (Split-Path $Report) | Out-Null
    @{
        status = 'Valid'; signer = $signature.SignerCertificate.Subject
        thumbprint = $signature.SignerCertificate.Thumbprint
        timestampSigner = $signature.TimeStamperCertificate.Subject
        sha256 = (Get-FileHash $Path -Algorithm SHA256).Hash.ToLower()
    } | ConvertTo-Json | Set-Content $Report -Encoding utf8
} finally {
    if ($pfx) { Remove-Item $pfx -Force -ErrorAction SilentlyContinue }
    foreach ($certificate in $imported) {
        if ($certificate.Thumbprint -notin $existingCertificates) {
            Remove-Item "Cert:\CurrentUser\My\$($certificate.Thumbprint)" -DeleteKey -Force -ErrorAction SilentlyContinue
        }
    }
}
