param(
  [string]$Model = (Join-Path $PSScriptRoot '..\model\germany_political_paths.smv'),
  [string]$NuXmv = 'C:\nuXmv-2.1.0-win64\nuXmv-2.1.0-win64\bin\nuXmv.exe',
  # Reaching PH_ELECT_DONE takes at most 47 transitions: the campaign,
  # three Reichstag decisions, and eight election rounds. PH_ELECT_DONE is
  # absorbing, so one BMC problem of this length also covers shorter paths.
  [int]$Bound = 50,
  [string]$TraceDir = (Join-Path $PSScriptRoot '..\traces'),
  [switch]$FailOnSeatDrift
)

$ErrorActionPreference = 'Stop'

New-Item -ItemType Directory -Force -Path $TraceDir | Out-Null

# The path reachability LTLSPECs in section 6 of the model. Each is checked by
# name, and nuXmv must report exactly the formula given here, so the script
# verifies these three formulas and nothing else. A formula being false is the
# success case: nuXmv's counterexample is a witness path that reaches
# PH_ELECT_DONE with the path condition satisfied. Expect lists the DEFINE
# values that the witness must show in that PH_ELECT_DONE state.
$checks = @(
  [pscustomobject]@{
    Key = 'democratic_union'
    Label = 'Democratic Union'
    Property = 'witness_dem_path_reachable'
    Formula = 'G !(phase = PH_ELECT_DONE & dem_win)'
    Expect = @{ dem_win = 'TRUE' }
  },
  [pscustomobject]@{
    Key = 'black_white_red'
    Label = 'Black-White-Red coalition'
    Property = 'witness_swr_path_reachable'
    Formula = 'G !(phase = PH_ELECT_DONE & swr_win)'
    Expect = @{ swr_win = 'TRUE' }
  },
  [pscustomobject]@{
    Key = 'schleicher'
    Label = 'Schleicher'
    Property = 'witness_schleicher_path_reachable'
    Formula = 'G !(phase = PH_ELECT_DONE & (!dem_win & !swr_win))'
    Expect = @{ dem_win = 'FALSE'; swr_win = 'FALSE' }
  }
)

# BDD variable order passed to nuXmv with -i. dem_win/swr_win compare a sum of
# 14 alignment-dependent seat counts with 223, and BMC booleanizes that
# comparison through BDDs. nuXmv's default order puts every align_* bit after
# every seats_* bit, which makes those BDDs explode (nuXmv 2.1.0 went past
# 6 GB before bound 0). With each align_X directly in front of its seats_X they
# stay proportional to the number of partial sums. nuXmv keeps the listed
# variables in this relative order and places the unlisted ones itself.
# The order changes only speed and memory, not results.
$bddVarOrder = @(
  'align_far_left', 'seats_far_left',
  'align_spd', 'seats_spd',
  'seats_lvp',
  'align_lvp_left', 'seats_lvp_left',
  'align_lvp_right', 'seats_lvp_right',
  'align_minor_lib', 'seats_minor_lib',
  'align_minority', 'seats_minority',
  'seats_zentrum',
  'align_zen_left', 'seats_zen_left',
  'align_zen_centre', 'seats_zen_centre',
  'align_zen_right', 'seats_zen_right',
  'align_guelph', 'seats_guelph',
  'align_agrarian', 'seats_agrarian',
  'align_dkp', 'seats_dkp',
  'align_dvlp', 'seats_dvlp',
  'align_far_right', 'seats_far_right'
)

$rawSeatVars = @(
  'seats_far_left',
  'seats_spd',
  'seats_lvp',
  'seats_guelph',
  'seats_minor_lib',
  'seats_minority',
  'seats_zentrum',
  'seats_agrarian',
  'seats_dkp',
  'seats_dvlp',
  'seats_far_right',
  'seats_schleicher_block'
)

$splitSeatVars = @(
  'seats_far_left',
  'seats_spd',
  'seats_lvp_left',
  'seats_lvp_right',
  'seats_minor_lib',
  'seats_minority',
  'seats_zen_left',
  'seats_zen_centre',
  'seats_zen_right',
  'seats_guelph',
  'seats_agrarian',
  'seats_dkp',
  'seats_dvlp',
  'seats_far_right',
  'seats_schleicher_block'
)

$splitTotalPhases = @('PH_ROUND_START', 'PH_ROUND_ACTION', 'PH_ROUND_END', 'PH_ELECT_DONE')
$expectedSeatTotal = 445
# seats_schleicher_block : 0..53 in the model, which saturates at 53.
$schleicherBlockMax = 53

function Invoke-NuXmv {
  param([string]$Property, [string]$OrderFile)

  # check_ltlspec_bmc_onepb solves one BMC problem of length $Bound. Plain
  # check_ltlspec_bmc solves every bound 0..$Bound and needed more than 6 GB
  # by bound 33. -l X leaves out loopbacks: G !p is a safety property, so a
  # loop-free path that reaches p is a complete witness; with loopbacks the
  # large dem_win/swr_win circuits kept bound 1 running for over 5 minutes.
  $commands = @(
    "read_model -i $Model",
    'go_bmc',
    "check_ltlspec_bmc_onepb -P $Property -k $Bound -l X",
    'quit'
  )

  $oldErrorActionPreference = $ErrorActionPreference
  $script:ErrorActionPreference = 'Continue'
  try {
    $commands |
      & $NuXmv -coi -i $OrderFile -int 2>&1 |
      ForEach-Object { $_.ToString() } |
      Where-Object { $_ -notmatch '^Warning: cannot assign value' }
  }
  finally {
    $script:ErrorActionPreference = $oldErrorActionPreference
  }
}

function Get-SpecResult {
  param([string[]]$Output)

  foreach ($line in $Output) {
    if ($line -match '-- specification\s+(.+?)\s+(?:IN\s+\S+\s+)?is\s+(true|false)\s*$') {
      return [pscustomobject]@{
        Formula = $matches[1]
        IsFalse = ($matches[2] -eq 'false')
      }
    }
  }

  return $null
}

function Compress-Formula {
  param([string]$Formula)

  return ($Formula -replace '\s+', '')
}

function Copy-State {
  param($State)

  $copy = @{}
  foreach ($key in $State.Keys) {
    $copy[$key] = $State[$key]
  }
  return $copy
}

function Read-TraceStates {
  param([string]$TracePath)

  $state = @{}
  $stateId = $null
  $states = New-Object System.Collections.Generic.List[object]
  foreach ($line in Get-Content -LiteralPath $TracePath) {
    if ($line -match '^\s*-> State: ([^<]+) <-') {
      if ($stateId) {
        $states.Add([pscustomobject]@{
            Id = $stateId
            Values = (Copy-State -State $state)
          })
      }
      $stateId = $matches[1].Trim()
      continue
    }

    if ($line -match '^\s+([A-Za-z_][A-Za-z0-9_]*) = (.+)$') {
      $state[$matches[1]] = $matches[2].Trim()
    }
  }

  if ($stateId) {
    $states.Add([pscustomobject]@{
        Id = $stateId
        Values = (Copy-State -State $state)
      })
  }

  Add-SchleicherBlockToTraceStates -TraceStates $states

  return $states
}

function Read-FinalState {
  param([string]$TracePath)

  $states = @(Read-TraceStates -TracePath $TracePath)
  if ($states.Count -eq 0) {
    return @{}
  }

  return $states[$states.Count - 1].Values
}

function Get-StateInt {
  param($State, [string]$Name)

  if ($State.ContainsKey($Name)) {
    return [int]$State[$Name]
  }

  return 0
}

function Get-StateSum {
  param($State, [string[]]$Names)

  $sum = 0
  foreach ($name in $Names) {
    $sum += Get-StateInt -State $State -Name $name
  }

  return $sum
}

function Get-SchleicherBlockGain {
  param($State)

  if ($State['phase'] -ne 'PH_ROUND_ACTION') {
    return 0
  }

  switch ($State['active_nf']) {
    'NF_FOMENT_DVLP' {
      return [int][Math]::Floor((Get-StateInt -State $State -Name 'seats_dvlp') * 15 / 100)
    }
    'NF_PROPAGANDA' {
      $dvlp = [int][Math]::Floor((Get-StateInt -State $State -Name 'seats_dvlp') * 20 / 100)
      $spd = [int][Math]::Floor((Get-StateInt -State $State -Name 'seats_spd') * 10 / 100)
      $dkp = [int][Math]::Floor((Get-StateInt -State $State -Name 'seats_dkp') * 10 / 100)
      return $dvlp + $spd + $dkp
    }
    default {
      return 0
    }
  }
}

# seats_schleicher_block is outside the cone of influence of the path formulas,
# so nuXmv does not print it; rebuild it the way the model's next() does.
function Add-SchleicherBlockToTraceStates {
  param($TraceStates)

  $block = 0
  for ($i = 0; $i -lt $TraceStates.Count; $i++) {
    $state = $TraceStates[$i].Values
    if ($state.ContainsKey('seats_schleicher_block')) {
      $block = [int]$state['seats_schleicher_block']
    }
    else {
      $state['seats_schleicher_block'] = "$block"
    }

    $gain = Get-SchleicherBlockGain -State $state
    if ($gain -gt 0) {
      $block = [Math]::Min($schleicherBlockMax, $block + $gain)
    }
  }
}

function Get-SeatAudit {
  param($State)

  $rawTotal = Get-StateSum -State $State -Names $rawSeatVars
  $splitTotal = Get-StateSum -State $State -Names $splitSeatVars
  $phase = $State['phase']
  $effectiveTotal = if ($splitTotalPhases -contains $phase) { $splitTotal } else { $rawTotal }

  [pscustomobject]@{
    RawTotal = $rawTotal
    SplitTotal = $splitTotal
    Total = $effectiveTotal
    Delta = $effectiveTotal - $expectedSeatTotal
  }
}

function Get-SeatDrifts {
  param($TraceStates)

  $drifts = New-Object System.Collections.Generic.List[object]
  $previous = $null
  foreach ($entry in $TraceStates) {
    $audit = Get-SeatAudit -State $entry.Values
    if ($previous -and $audit.Total -ne $previous.Total) {
      $drifts.Add([pscustomobject]@{
          State = $entry.Id
          Phase = $entry.Values['phase']
          Round = $entry.Values['round']
          PreviousTotal = $previous.Total
          Total = $audit.Total
          Delta = $audit.Total - $previous.Total
          RawTotal = $audit.RawTotal
          SplitTotal = $audit.SplitTotal
        })
    }
    $previous = $audit
  }

  return $drifts
}

function Format-SignedInt {
  param([int]$Value)

  if ($Value -gt 0) {
    return "+$Value"
  }

  return "$Value"
}

$failed = $false
Write-Host '=== Outcome reachability checks ==='
Write-Host ("Model: {0}" -f $Model)
Write-Host ("Bound: {0}" -f $Bound)

$orderFile = Join-Path $TraceDir 'bdd_var_order.ord'
$bddVarOrder | Set-Content -LiteralPath $orderFile -Encoding ASCII

foreach ($check in $checks) {
  $tracePath = Join-Path $TraceDir ("{0}_trace.txt" -f $check.Key)
  $output = @(Invoke-NuXmv -Property $check.Property -OrderFile $orderFile)
  $nuXmvExitCode = $LASTEXITCODE
  $output | Set-Content -LiteralPath $tracePath -Encoding UTF8

  $spec = Get-SpecResult -Output $output
  if (-not $spec) {
    if ($output -match 'no counterexample found with bound') {
      Write-Host ("FAIL not reached: {0}: {1} has no counterexample up to bound {2} (trace={3})" -f $check.Label, $check.Formula, $Bound, $tracePath)
    }
    else {
      $reason = @($output | Where-Object { $_ -match 'No property named|error' } | Select-Object -First 1)
      if ($reason.Count -eq 0) {
        $reason = @($output | Where-Object { $_.Trim() } | Select-Object -Last 1)
      }
      if ($reason.Count -eq 0) {
        $reason = @('no output')
      }
      Write-Host ("FAIL nuXmv: {0} ({1}): {2} (exit={3}, trace={4})" -f $check.Label, $check.Property, $reason[0].Trim(), $nuXmvExitCode, $tracePath)
    }
    $failed = $true
    continue
  }

  if ((Compress-Formula $spec.Formula) -cne (Compress-Formula $check.Formula)) {
    Write-Host ("FAIL wrong formula: {0}: {1} is {2} in the model, expected {3}" -f $check.Label, $check.Property, $spec.Formula, $check.Formula)
    $failed = $true
    continue
  }

  if (-not $spec.IsFalse) {
    Write-Host ("FAIL not reached: {0}: {1} is true (trace={2})" -f $check.Label, $spec.Formula, $tracePath)
    $failed = $true
    continue
  }

  $traceStates = @(Read-TraceStates -TracePath $tracePath)
  if ($traceStates.Count -eq 0) {
    Write-Host ("FAIL bad witness: {0}: nuXmv reported false but printed no trace states (trace={1})" -f $check.Label, $tracePath)
    $failed = $true
    continue
  }

  # The counterexample violates the formula at the first state that is in
  # PH_ELECT_DONE with the path condition, as evaluated by the model's DEFINEs.
  # A one-problem BMC trace may go on for a few states after that.
  $witness = $null
  foreach ($entry in $traceStates) {
    if ($entry.Values['phase'] -cne 'PH_ELECT_DONE') {
      continue
    }
    $holds = $true
    foreach ($name in $check.Expect.Keys) {
      if ($entry.Values[$name] -cne $check.Expect[$name]) {
        $holds = $false
      }
    }
    if ($holds) {
      $witness = $entry
      break
    }
  }

  $state = $traceStates[$traceStates.Count - 1].Values
  if ($witness) {
    $state = $witness.Values
  }

  $audit = Get-SeatAudit -State $state
  $totalDeltaText = Format-SignedInt -Value $audit.Delta
  $drifts = @(Get-SeatDrifts -TraceStates $traceStates)
  $seatText = "DEM={0}, SWR={1}, TOTAL={2}, TOTAL_DELTA={3}, trace={4}" -f $state['dem_seats'], $state['swr_seats'], $audit.Total, $totalDeltaText, $tracePath

  if ($witness) {
    Write-Host ("OK   reachable: {0}: {1} is false at state {2} ({3})" -f $check.Label, $spec.Formula, $witness.Id, $seatText)
  }
  else {
    $finalValues = @()
    foreach ($name in (@('phase') + @($check.Expect.Keys))) {
      $finalValues += ("{0}={1}" -f $name, $state[$name])
    }
    Write-Host ("FAIL bad witness: {0}: no trace state is PH_ELECT_DONE with the path condition; final state has {1} ({2})" -f $check.Label, ($finalValues -join ', '), $seatText)
    $failed = $true
  }

  if ($drifts.Count -gt 0) {
    foreach ($drift in ($drifts | Select-Object -First 5)) {
      $transitionDeltaText = Format-SignedInt -Value $drift.Delta
      Write-Host ("WARN seat drift: {0} state={1} phase={2} round={3} total {4}->{5} ({6}) raw={7} split={8}" -f $check.Label, $drift.State, $drift.Phase, $drift.Round, $drift.PreviousTotal, $drift.Total, $transitionDeltaText, $drift.RawTotal, $drift.SplitTotal)
    }

    if ($drifts.Count -gt 5) {
      Write-Host ("WARN seat drift: {0} additional drift rows omitted: {1}" -f $check.Label, ($drifts.Count - 5))
    }

    if ($FailOnSeatDrift) {
      $failed = $true
    }
  }
}

if ($failed) {
  exit 1
}
