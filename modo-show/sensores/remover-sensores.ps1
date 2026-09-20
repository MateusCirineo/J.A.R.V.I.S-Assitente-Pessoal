# Desfaz instalar-sensores.ps1. Precisa de administrador.
# O driver PawnIO fica (outros programas, como o LibreHardwareMonitor, usam);
# para tira-lo tambem: remover-sensores.ps1 -TambemPawnIO <PawnIO_setup.exe>
param([string]$TambemPawnIO)

$ErrorActionPreference = 'Continue'
Stop-ScheduledTask -TaskName 'Jarvis Sensores' -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'Jarvis Sensores' -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" |
    Where-Object { $_.CommandLine -like '*Jarvis Sensores\sensores.ps1*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Remove-Item (Join-Path $env:ProgramFiles 'Jarvis Sensores') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $env:ProgramData 'JarvisSensores') -Recurse -Force -ErrorAction SilentlyContinue
if ($TambemPawnIO) { Start-Process $TambemPawnIO -ArgumentList '-uninstall', '-silent' -Wait }
'removido'
