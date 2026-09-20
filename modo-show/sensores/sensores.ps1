# Leitor de sensores do Jarvis: temperatura e potencia da CPU.
#
# Roda como SYSTEM (tarefa agendada "Jarvis Sensores") porque o Windows so
# libera esses registradores da CPU para administrador. Usa a biblioteca do
# LibreHardwareMonitor com o driver assinado PawnIO. Nao abre porta de rede:
# grava um JSON em %ProgramData%\JarvisSensores, que o runtime do HUD (usuario
# comum) apenas le.
param([switch]$UmaVez, [string]$Saida)

$ErrorActionPreference = 'Stop'
$script:lib = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'lib'

# Sem o .config do LibreHardwareMonitor.exe as versoes das dependencias podem
# nao bater; resolve pelo nome a partir da pasta lib.
[AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($remetente, $evento)
    $nome = (New-Object Reflection.AssemblyName $evento.Name).Name
    $dll = Join-Path $script:lib "$nome.dll"
    if (Test-Path $dll) { return [Reflection.Assembly]::LoadFrom($dll) }
    return $null
})
Add-Type -Path (Join-Path $script:lib 'LibreHardwareMonitorLib.dll')

if (-not $Saida) { $Saida = Join-Path $env:ProgramData 'JarvisSensores\sensores.json' }
$pasta = Split-Path -Parent $Saida
if (-not (Test-Path $pasta)) { New-Item -ItemType Directory -Force $pasta | Out-Null }
[Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal'

$pc = New-Object LibreHardwareMonitor.Hardware.Computer
$pc.IsCpuEnabled = $true
$pc.Open()

function Valor($v) {
    if ($null -eq $v -or [single]::IsNaN($v)) { return $null }
    return [math]::Round([double]$v, 2)
}

$inicio = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
$relogio = [Diagnostics.Stopwatch]::StartNew()
$anterior = $null
$energia = 0.0
$utf8 = New-Object Text.UTF8Encoding $false

while ($true) {
    try {
        $temps = [ordered]@{}
        $pots = [ordered]@{}
        $nomeCpu = $null
        foreach ($hw in $pc.Hardware) {
            if ($hw.HardwareType -ne [LibreHardwareMonitor.Hardware.HardwareType]::Cpu) { continue }
            $hw.Update()
            $nomeCpu = $hw.Name
            foreach ($s in $hw.Sensors) {
                $v = Valor $s.Value
                if ($null -eq $v) { continue }
                if ($s.SensorType -eq [LibreHardwareMonitor.Hardware.SensorType]::Temperature) { $temps[$s.Name] = $v }
                elseif ($s.SensorType -eq [LibreHardwareMonitor.Hardware.SensorType]::Power) { $pots[$s.Name] = $v }
            }
        }
        # A potencia do pacote e a media desde a leitura anterior (contador RAPL),
        # entao somar potencia x intervalo reproduz a energia medida.
        $agora = $relogio.Elapsed.TotalSeconds
        $pacote = $pots['CPU Package']
        if ($null -ne $anterior -and $null -ne $pacote) { $energia += $pacote * ($agora - $anterior) }
        $anterior = $agora

        $json = [ordered]@{
            versao           = 1
            em               = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
            desde            = $inicio
            intervalo_s      = 1
            cpu              = $nomeCpu
            temperaturas_c   = $temps
            potencias_w      = $pots
            energia_pacote_j = [math]::Round($energia, 3)
        } | ConvertTo-Json -Depth 4 -Compress

        if ($UmaVez) { $json; break }
        $tmp = "$Saida.tmp"
        [IO.File]::WriteAllText($tmp, $json, $utf8)
        # o runtime pode estar lendo neste instante: tenta de novo no proximo ciclo
        try { Move-Item -Force $tmp $Saida } catch { }
    } catch {
        if ($UmaVez) { throw }
    }
    Start-Sleep -Milliseconds 1000
}
