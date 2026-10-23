#Requires -Version 5.1
<# Developer-only workflow. NOT called by the addon or its download endpoint.
   A trusted code-signing certificate/private-key provider must already be installed.
   Never supply a PFX/password to this repository. No trust-store or warning bypass. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InputFile,
    [Parameter(Mandatory=$true)][string]$OutputFile,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Fa-f0-9]{40}$')][string]$Thumbprint,
    [Parameter(Mandatory=$true)][uri]$GatewayOrigin,
    [Parameter(Mandatory=$true)][uri]$TimestampUrl,
    [ValidateSet('CurrentUser','LocalMachine')][string]$StoreLocation='CurrentUser',
    [string]$SignTool='signtool.exe',
    [string]$BuildRecord=(Join-Path $PSScriptRoot '../docs/WINDOWS-BUILD.json')
)
$ErrorActionPreference='Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Run this workflow on Windows with the Windows SDK SignTool installed.' }
foreach ($u in @($GatewayOrigin,$TimestampUrl)) {
    if (-not $u.IsAbsoluteUri -or $u.Scheme -ne 'https' -or $u.UserInfo -or $u.Fragment) { throw 'Gateway and timestamp URLs must be HTTPS without credentials/fragments.' }
}
if ($GatewayOrigin.AbsolutePath -ne '/' -or $GatewayOrigin.Query) { throw 'GatewayOrigin must be an HTTPS origin, not an enrollment link.' }
$inputPath=[IO.Path]::GetFullPath($InputFile);$outputPath=[IO.Path]::GetFullPath($OutputFile)
if ($inputPath -eq $outputPath -or (Test-Path -LiteralPath $outputPath)) { throw 'Output must be a NEW file, distinct from the unsigned input.' }
$item=Get-Item -LiteralPath $inputPath
if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.Extension -ne '.exe' -or $item.Length -gt 33554432) { throw 'Input must be a regular, bounded personalized EXE.' }
# Validate exactly the approved unsigned worker bytes before trusting its metadata.
$record=Get-Content -LiteralPath $BuildRecord -Raw | ConvertFrom-Json
if ($record.signed -ne $false -or $record.companyName -ne 'Robo Universal') { throw 'Select the approved unsigned Robo Universal build record.' }
$raw=[IO.File]::ReadAllBytes($inputPath);$baseLength=[int]$record.bytes
if ($baseLength -lt 256 -or $raw.Length -le $baseLength+21) { throw 'A personalized enrollment download is required, not the generic template.' }
$sha=[Security.Cryptography.SHA256]::Create()
try { $prefixHash=([BitConverter]::ToString($sha.ComputeHash($raw,0,$baseLength))).Replace('-','').ToLowerInvariant() } finally { $sha.Dispose() }
if ($prefixHash -ne $record.binarySha256) { throw 'Input does not match the approved worker build. Do not sign modified or unreviewed code.' }
$magic=[Text.Encoding]::ASCII.GetBytes('ROBOCLOUD-ENROLL-V1');$trailerStart=$raw.Length-$magic.Length-4
if ([Text.Encoding]::ASCII.GetString($raw,$trailerStart+4,$magic.Length) -ne 'ROBOCLOUD-ENROLL-V1') { throw 'Missing final enrollment trailer. Do not sign a generic/already signed EXE.' }
$length=[BitConverter]::ToUInt32($raw,$trailerStart)
if ($length -lt 1 -or $length -gt 16384 -or $trailerStart-$length -ne $baseLength) { throw 'Invalid enrollment bounds.' }
$payload=[Text.Encoding]::UTF8.GetString($raw,$baseLength,$length) | ConvertFrom-Json
if ($payload.url.TrimEnd('/') -ne $GatewayOrigin.AbsoluteUri.TrimEnd('/') -or -not $payload.enrollment -or $payload.id -notmatch '^[a-f0-9]{16,64}$') { throw 'Enrollment does not belong to the approved gateway origin.' }
$cert=Get-Item -LiteralPath ("Cert:\"+$StoreLocation+"\My\"+$Thumbprint)
if (-not $cert.HasPrivateKey -or (Get-Date) -lt $cert.NotBefore -or (Get-Date) -gt $cert.NotAfter) { throw 'A current certificate with an accessible private-key provider is required.' }
$publisher=$cert.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false)
if ($publisher -cne 'Robo Universal') { throw 'Certificate publisher must actually be Robo Universal. Metadata cannot substitute for its certified identity.' }
$ekuExtensions=@($cert.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.37' })
$codeSigning=@()
if ($ekuExtensions.Count -gt 0) { $eku=[Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$ekuExtensions[0]; $codeSigning=@($eku.EnhancedKeyUsages | Where-Object { $_.Value -eq '1.3.6.1.5.5.7.3.3' }) }
if ($codeSigning.Count -eq 0) { throw 'Certificate is not enabled for code signing.' }
$tool=(Get-Command $SignTool -CommandType Application -ErrorAction Stop).Source
$folder=Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $folder -PathType Container)) { throw 'Create a private output directory first.' }
$temp=Join-Path $folder ('.robo-signing-'+[guid]::NewGuid().ToString('N')+'.exe')
try {
    # Stage the exact bytes inspected above, avoiding an input-file replacement race.
    [IO.File]::WriteAllBytes($temp,$raw)
    $signArgs=@('sign','/sha1',$Thumbprint,'/s','My','/fd','SHA256','/tr',$TimestampUrl.AbsoluteUri,'/td','SHA256','/d','Robo Cloud Enrollment')
    if ($StoreLocation -eq 'LocalMachine') { $signArgs+=@('/sm') }
    $signArgs+=@($temp)
    & $tool @signArgs
    if ($LASTEXITCODE -ne 0) { throw 'SignTool signing failed; no output was published.' }
    & $tool verify /pa /all /v $temp
    if ($LASTEXITCODE -ne 0) { throw 'Authenticode trust verification failed; no output was published.' }
    $signature=Get-AuthenticodeSignature -LiteralPath $temp
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $Thumbprint -or $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false) -cne 'Robo Universal') { throw 'Signature is not trusted for the requested publisher/certificate.' }
    [IO.File]::Move($temp,$outputPath)
    Write-Output 'Signed final personalized installer and verified its Authenticode trust. Do not change its bytes or append data.'
} finally {
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
}
