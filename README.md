# Model Checking Complex Branching Scenarios in Strategy Games — Artifact

This repository contains the nuXmv model, the verification script, the
counterexample traces, and the analysis scripts for the paper
"Model Checking Complex Branching Scenarios in Strategy Games".
The model covers the German minigames "Reichstag Elections of 1936" and
"Kabinett Schleicher" of Kaiserreich, a mod for Hearts of Iron IV.

## Contents

```
model/
  germany_political_paths.smv     SMV model (Section IV); LTLSPECs at the end
scripts/
  check_path_reachability.ps1     runs nuXmv on the three path properties and
                                  checks the terminal state of each witness (Section V)
traces/
  democratic_union_trace.txt      counterexample for witness_dem_path_reachable
  black_white_red_trace.txt       counterexample for witness_swr_path_reachable
  schleicher_trace.txt            counterexample for witness_schleicher_path_reachable
analysis/
  tracelib.py                     shared trace parser and file locations
  analyze_traces.py               trace analysis of Sec. IV-G; numbers of Tables IV and VI
  check_event_orders.py           event-order abstraction of Sec. IV-C
  check_domain_bounds.py          tightened seat domains are never exceeded (Sec. IV-G)
  model_stats.py                  model size and approximate cone of influence (Secs. IV-G, V)
```

## Requirements

- nuXmv 2.1.0 (download from https://nuxmv.fbk.eu; not included)
- PowerShell 5.1 or later (for `scripts/check_path_reachability.ps1`)
- Python 3.8 or later, standard library only (for `analysis/`)

## Reproducing the results

1. Model checking (overwrites the files in `traces/`):

   ```
   powershell -ExecutionPolicy Bypass -File scripts\check_path_reachability.ps1 -NuXmv <path to nuXmv.exe>
   ```

   The script solves one BMC problem of length 50 without loopbacks for each
   property (`check_ltlspec_bmc_onepb -k 50 -l X`), with COI reduction and the
   interleaved variable order written to `traces/bdd_var_order.ord`. Each
   property is expected to be false; the counterexample is the witness.

2. Analysis (works on the traces in `traces/`):

   ```
   cd analysis
   python analyze_traces.py --rounds
   python check_event_orders.py
   python check_domain_bounds.py
   python model_stats.py
   ```

## Correspondence to the paper

| Paper                                  | Command / file                        |
|----------------------------------------|---------------------------------------|
| Path properties (Sec. IV-G)            | LTLSPECs `witness_*_path_reachable` in the model |
| Variable order, BMC setup (Sec. IV-G)  | `scripts/check_path_reachability.ps1` |
| 27 feasible event orders (Sec. IV-C)   | `analysis/check_event_orders.py`      |
| Domain bounds, 183 state bits          | `analysis/check_domain_bounds.py`, `analysis/model_stats.py` |
| Table IV, trace analysis               | `analysis/analyze_traces.py`          |
| Table VI                               | `analysis/analyze_traces.py --rounds` |

## License

The model, scripts, and analysis code in this repository are released under
the MIT License (see `LICENSE`). Kaiserreich and Hearts of Iron IV are the
property of their respective owners; this repository contains no game or mod
files, only a model written by the authors from the publicly available mod
scripts.
