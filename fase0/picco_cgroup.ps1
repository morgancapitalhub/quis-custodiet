# Fase 0 - prova di misurabilita' del picco di memoria del cgroup (non e' codice del progetto).
# Il "candidato" (opzioni del brief) alloca N MiB con pagine toccate, le libera, segnala FATTO e resta vivo.
# Un osservatore SEPARATO e persistente (altro container, cgroupfs della VM in sola lettura) legge memory.peak.
param([int[]]$Sizes = @(0, 100, 300, 600), [int]$Reps = 3)
$opts = @('--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
          '--pids-limit','64','--memory','1g','--memory-swap','1g','--cpus','1','--user','65534:65534',
          '--tmpfs','/tmp:rw,size=64m')
$py = 'import sys,time; n=int(sys.argv[1]); b=bytearray(n*1048576); del b; print(chr(70)+chr(65)+chr(84)+chr(84)+chr(79),flush=True); time.sleep(120)'
$obs = docker run -d --rm --network none -v /sys/fs/cgroup:/cg:ro alpine:3 sleep 3600
"MiB_allocati`trip`tpeak_MiB`tcurrent_MiB`tpeak-base_MiB`toom_kill"
$base = $null
foreach ($n in $Sizes) { foreach ($r in 1..$Reps) {
  $id = docker run -d --rm @opts python:3.11-slim python -c $py $n
  $t0 = Get-Date
  do { Start-Sleep -Milliseconds 300 } until (((docker logs $id 2>$null) -match 'FATTO') -or ((Get-Date) - $t0).TotalSeconds -gt 60)
  $out = docker exec $obs sh -c "cat /cg/docker/$id/memory.peak /cg/docker/$id/memory.current; grep oom_kill /cg/docker/$id/memory.events"
  docker rm -f $id | Out-Null
  if ($out.Count -lt 3) { "$n`t$r`tERRORE: $out"; continue }
  $peak = [math]::Round([double]$out[0]/1MB,1); $cur = [math]::Round([double]$out[1]/1MB,1)
  if ($n -eq 0 -and $null -eq $base) { $base = $peak }
  "$n`t$r`t$peak`t$cur`t$([math]::Round($peak-$base,1))`t$(($out[2] -split ' ')[1])"
}}
docker rm -f $obs | Out-Null
