"""Trace analysis of Section IV-G and the numbers of Tables IV and VI.

For each witness trace this script reports
  * the depth at which PH_ELECT_DONE is first reached,
  * whether the reported dem_seats/swr_seats agree with seats and affiliations,
  * the first state (from E-K01 on) in which a coalition holds >= 223 seats,
    the maximum seats of the competing coalition up to that state, and
    whether the majority is kept until the terminal state,
  * whether the path is decided along the trace (no competing decision earlier;
    for the Schleicher government path, no majority before Round 8 is entered),
  * the seat total in every state, counting the Schleicher bloc, which is
    outside the cone of influence and is reconstructed from the NF effects.
With --rounds, a round-by-round summary (Table VI) is printed as well.

Usage: python analyze_traces.py [--rounds]"""
import sys
from tracelib import TRACES, parse_trace

MAJORITY, TOTAL = 223, 445
SPLIT = ['far_left', 'spd', 'lvp_left', 'lvp_right', 'minor_lib', 'minority', 'zen_left',
         'zen_centre', 'zen_right', 'guelph', 'agrarian', 'dkp', 'dvlp', 'far_right']
RAW = ['far_left', 'spd', 'lvp', 'guelph', 'minor_lib', 'minority', 'zentrum', 'agrarian',
       'dkp', 'dvlp', 'far_right']
KABINETT = {'PH_ROUND_START', 'PH_ROUND_ACTION', 'PH_ROUND_END', 'PH_ELECT_DONE'}
TARGET_VAR = {'LVP_LEFT': 'lvp_left', 'LVP_RIGHT': 'lvp_right', 'ZEN_LEFT': 'zen_left',
              'ZEN_CENTRE': 'zen_centre', 'ZEN_RIGHT': 'zen_right', 'MINORITY': 'minority',
              'MINOR_LIB': 'minor_lib', 'GUELPH': 'guelph', 'AGRARIAN': 'agrarian', 'DKP': 'dkp'}

def side_seats(s, side):
    return sum(int(s['seats_' + f]) for f in SPLIT if s['align_' + f] == str(side))

def bloc_series(S):
    """Schleicher bloc per state: seats removed from SPD/DVLP/DkP by NF effects."""
    out, bloc = [], 0
    for i, s in enumerate(S):
        out.append(bloc)
        if s['phase'] == 'PH_ROUND_ACTION' and i + 1 < len(S):
            bloc += sum(int(s['seats_' + f]) - int(S[i + 1]['seats_' + f]) for f in ('spd', 'dvlp', 'dkp'))
    return out

def analyze(name, S):
    done = next(i for i, s in enumerate(S) if s['phase'] == 'PH_ELECT_DONE')
    mismatch = [i for i, s in enumerate(S)
                if int(s['dem_seats']) != side_seats(s, 1) or int(s['swr_seats']) != side_seats(s, 2)]
    bloc = bloc_series(S)
    totals = {sum(int(s['seats_' + f]) for f in (SPLIT if s['phase'] in KABINETT else RAW)) + bloc[i]
              for i, s in enumerate(S)}
    kab = [i for i, s in enumerate(S) if s['phase'] in KABINETT | {'PH_EV_NATIONAL_STABILITY'} and i <= done]
    dem = {i: int(S[i]['dem_seats']) for i in kab}
    swr = {i: int(S[i]['swr_seats']) for i in kab}
    # states before Round 8 is entered (Round 8 starts with round = 8)
    before_r8 = [i for i in kab if S[i]['round'] != '8']
    first = next((i for i in kab if dem[i] >= MAJORITY or swr[i] >= MAJORITY), None)

    print(f'== {name}')
    print(f'  PH_ELECT_DONE first reached at depth {done} (state 1.{done + 1}); trace length {len(S) - 1}')
    print(f'  seat sums consistent with seats/affiliations: {not mismatch}')
    print(f'  seat total incl. Schleicher bloc: {sorted(totals)} (expected {TOTAL}); final bloc {bloc[done]}')
    if first is None:
        decided = all(dem[i] < MAJORITY and swr[i] < MAJORITY for i in before_r8)
        print(f'  no majority; max DU/BWR seats {max(dem.values())}/{max(swr.values())}')
        print(f'  Schleicher government path decided: {decided}')
    else:
        win, rival = (dem, swr) if dem[first] >= MAJORITY else (swr, dem)
        label = 'DU' if win is dem else 'BWR'
        upto = [i for i in kab if i <= first]
        kept = all(win[i] >= MAJORITY for i in kab if i >= first)
        decided = first in before_r8 and all(rival[i] < MAJORITY for i in upto)
        print(f'  first majority: {label} {win[first]} seats at state 1.{first + 1} '
              f'({S[first]["phase"]}, round {S[first]["round"]})')
        print(f'  max rival seats up to then: {max(rival[i] for i in upto)}; majority kept to the end: {kept}')
        print(f'  {label} path decided (no earlier competing decision, before Round 8): {decided}')
    print(f'  final DU/BWR seats: {dem[done]}/{swr[done]}')

def rounds(S, I):
    print('  R  NF                   protected                                  DU target         BWR target        DU/BWR')
    for i, s in enumerate(S):
        if s['phase'] != 'PH_ROUND_START':
            continue
        st, act, ai, end = I[i], S[i + 1], I[i + 1], S[i + 2]
        def res(t, side):
            if t == 'NONE':
                return '--'
            v = 'align_' + TARGET_VAR[t]
            return t + (' ok' if end[v] == str(side) and act[v] != str(side) else ' x')
        prot = [ai['protect_%d' % k] for k in range(1, 6) if ai['protect_%d' % k] != 'NONE']
        extra = []
        if st.get('vc_choice', 'VC_NONE') != 'VC_NONE': extra.append(st['vc_choice'])
        if st.get('center_result', 'CENTER_NONE') != 'CENTER_NONE': extra.append(st['center_result'])
        print(f'  {s["round"]}  {st["nf_choice"]:20s} {",".join(prot):42s} {res(ai["target_dem"], 1):17s} '
              f'{res(ai["target_swr"], 2):17s} {end["dem_seats"]}/{end["swr_seats"]}  {" ".join(extra)}')

if __name__ == '__main__':
    for name, path in TRACES.items():
        S, I = parse_trace(path)
        analyze(name, S)
        if '--rounds' in sys.argv:
            rounds(S, I)
