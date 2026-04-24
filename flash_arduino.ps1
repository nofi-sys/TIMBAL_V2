[CmdletBinding()]
param(
    [string]$Sketch = (Join-Path $PSScriptRoot 'arduino\HOST_ANALOG_STREAM_EXPERIMENT.ino'),
    [string]$Port,
    [string]$Fqbn,
    [switch]$CompileOnly,
    [switch]$UploadOnly,
    [switch]$VerboseCli
)

$ErrorActionPreference = 'Stop'

function Find-ArduinoCli {
    $localAppData = $env:LOCALAPPDATA
    $programFiles = $env:ProgramFiles
    $candidates = @(
        (Get-Command arduino-cli -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        (Join-Path $localAppData 'Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'),
        (Join-Path $programFiles 'Arduino CLI\arduino-cli.exe')
    ) | Where-Object { $_ }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw 'No encontre arduino-cli. Instala Arduino IDE 2.x o arduino-cli.'
}

function Stage-Sketch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath
    )

    $resolved = (Resolve-Path -LiteralPath $InputPath).Path
    $item = Get-Item -LiteralPath $resolved

    if ($item.PSIsContainer) {
        return $resolved
    }

    if ($item.Extension -ne '.ino') {
        throw "El sketch debe ser una carpeta o un archivo .ino. Recibi: $resolved"
    }

    $name = [System.IO.Path]::GetFileNameWithoutExtension($item.Name)
    $tempRoot = Join-Path $env:TEMP 'timbal-arduino-sketches'
    $stageDir = Join-Path $tempRoot $name

    if (Test-Path -LiteralPath $stageDir) {
        Remove-Item -LiteralPath $stageDir -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $stageDir | Out-Null
    Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $stageDir "$name.ino")

    $auxExtensions = @('.h', '.hpp', '.hh', '.c', '.cc', '.cpp', '.cxx', '.ipp', '.tpp', '.inc', '.s', '.S')
    Get-ChildItem -LiteralPath $item.DirectoryName -File | ForEach-Object {
        if ($_.FullName -eq $item.FullName) {
            return
        }
        if ($auxExtensions -contains $_.Extension) {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $stageDir $_.Name)
        }
    }

    return $stageDir
}

function Get-DetectedBoard {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CliPath
    )

    $json = & $CliPath board list --json
    if (-not $json) {
        return $null
    }

    $data = $json | ConvertFrom-Json
    $ports = @($data.detected_ports)
    if (-not $ports) {
        return $null
    }

    if ($Port) {
        $ports = @($ports | Where-Object { $_.port.address -eq $Port })
    }

    $ports = @($ports | Where-Object { $_.matching_boards -and $_.matching_boards.Count -gt 0 })
    if (-not $ports) {
        return $null
    }

    $preferred = @(
        $ports | Where-Object {
            $_.matching_boards[0].fqbn -eq 'arduino:avr:leonardo' -or
            $_.matching_boards[0].name -match 'Leonardo'
        }
    )

    $selected = if ($preferred) { $preferred[0] } else { $ports[0] }
    return [pscustomobject]@{
        Port = $selected.port.address
        Fqbn = $selected.matching_boards[0].fqbn
        Name = $selected.matching_boards[0].name
    }
}

$cli = Find-ArduinoCli
$stagedSketch = Stage-Sketch -InputPath $Sketch
$detected = Get-DetectedBoard -CliPath $cli

if (-not $Fqbn) {
    if ($detected -and $detected.Fqbn) {
        $Fqbn = $detected.Fqbn
    }
    else {
        $Fqbn = 'arduino:avr:leonardo'
    }
}

if (-not $CompileOnly -and -not $Port) {
    if ($detected -and $detected.Port) {
        $Port = $detected.Port
    }
}

Write-Host "[flash] CLI: $cli"
Write-Host "[flash] Sketch: $stagedSketch"
Write-Host "[flash] FQBN: $Fqbn"
if ($Port) {
    Write-Host "[flash] Port: $Port"
}

if (-not $UploadOnly) {
    $compileArgs = @('compile', '--fqbn', $Fqbn, $stagedSketch)
    if ($VerboseCli) {
        $compileArgs += '--verbose'
    }
    & $cli @compileArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

if (-not $CompileOnly) {
    if (-not $Port) {
        throw 'No pude detectar el puerto del Arduino. Usa -Port COMx.'
    }

    $uploadArgs = @('upload', '--fqbn', $Fqbn, '-p', $Port, $stagedSketch)
    if ($VerboseCli) {
        $uploadArgs += '--verbose'
    }
    & $cli @uploadArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Write-Host '[flash] OK'
