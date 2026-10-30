param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8765,
    [switch]$Offline,
    [string]$Python = (Join-Path $env:USERPROFILE '.venv\Scripts\python.exe')
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python-Umgebung nicht gefunden: $Python. Den vorhandenen Interpreter mit -Python angeben."
}
$mainPath = Join-Path $PSScriptRoot 'main.py'
$launchArguments = @($mainPath, 'serve', '--port', $Port)
if ($Offline) {
    $launchArguments += '--offline'
}
& $Python @launchArguments
exit $LASTEXITCODE
