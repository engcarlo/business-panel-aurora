# Cria a tarefa "Aurora - Rotina de segunda" no Agendador de Tarefas do Windows:
# toda segunda-feira às 09:00, roda `python -m aurora semana` na pasta Projeto 1.
# Para remover:  Unregister-ScheduledTask -TaskName "Aurora - Rotina de segunda" -Confirm:$false
$projeto = Split-Path -Parent $PSScriptRoot
$python  = (Get-Command python).Source
$acao    = New-ScheduledTaskAction -Execute $python -Argument "-m aurora semana" -WorkingDirectory $projeto
$gatilho = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9:00am
$config  = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "Aurora - Rotina de segunda" -Action $acao -Trigger $gatilho -Settings $config `
    -Description "Controle de Recebimentos Aurora - ver ROTINA_SEGUNDA.md" -Force
