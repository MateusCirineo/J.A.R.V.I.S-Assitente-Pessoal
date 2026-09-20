# Instala o leitor de sensores do Jarvis. Precisa de administrador; roda uma vez.
#
# - copia o leitor e a biblioteca do LibreHardwareMonitor para Program Files
#   (so administradores escrevem ali, entao ninguem troca o script que roda
#   como SYSTEM)
# - instala o driver assinado PawnIO (o mesmo que o LibreHardwareMonitor usa)
# - cria a tarefa "Jarvis Sensores" (SYSTEM, ao ligar o PC) e a inicia
#
# Desfazer: remover-sensores.ps1
param([Parameter(Mandatory)][string]$Origem, [Parameter(Mandatory)][string]$PawnIO)

$ErrorActionPreference = 'Stop'
$dados = Join-Path $env:ProgramData 'JarvisSensores'
New-Item -ItemType Directory -Force $dados | Out-Null
# SYSTEM e Administradores escrevem; usuarios so leem
icacls $dados /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' | Out-Null
Start-Transcript -Path (Join-Path $dados 'instalacao.log') -Force | Out-Null

try {
    $destino = Join-Path $env:ProgramFiles 'Jarvis Sensores'
    New-Item -ItemType Directory -Force (Join-Path $destino 'lib') | Out-Null
    Copy-Item (Join-Path $Origem '*.dll') (Join-Path $destino 'lib') -Force
    Copy-Item (Join-Path $PSScriptRoot 'sensores.ps1') $destino -Force
    "copiado para $destino"

    $assinatura = Get-AuthenticodeSignature $PawnIO
    if ($assinatura.Status -ne 'Valid' -or $assinatura.SignerCertificate.Subject -notmatch 'CN=namazso\.eu') {
        throw "instalador do PawnIO sem assinatura valida do autor: $($assinatura.Status)"
    }
    $p = Start-Process $PawnIO -ArgumentList '-install', '-silent' -Wait -PassThru
    "PawnIO: codigo $($p.ExitCode) (0 = ok, 3010 = pede reinicio)"

    $acao = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$destino\sensores.ps1`"" `
        -WorkingDirectory $destino
    $gatilho = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
    $cfg = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName 'Jarvis Sensores' -Action $acao -Trigger $gatilho -Principal $principal `
        -Settings $cfg -Description 'Temperatura e potencia da CPU para o HUD do Jarvis (sem rede).' -Force | Out-Null
    Start-ScheduledTask -TaskName 'Jarvis Sensores'
    'tarefa criada e iniciada'
} catch {
    "ERRO: $($_.Exception.Message)"
    exit 1
} finally {
    Stop-Transcript | Out-Null
}
