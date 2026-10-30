"""Common helpers: locate repository files and parse nuXmv counterexample traces.

nuXmv prints only the variables that changed, so every state is completed with
the values of the previous one. inputs[i] is the input of the transition that
leads from states[i] to states[i+1]."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / 'model' / 'germany_political_paths.smv'
TRACES = {
    'Democratic Union': ROOT / 'traces' / 'democratic_union_trace.txt',
    'Black-White-Red Coalition': ROOT / 'traces' / 'black_white_red_trace.txt',
    'Schleicher government': ROOT / 'traces' / 'schleicher_trace.txt',
}

def read_model_text(strip_comments=True):
    src = MODEL.read_text(encoding='utf-8').replace('\r\n', '\n')
    return re.sub(r'--[^\n]*', '', src) if strip_comments else src

def parse_trace(path):
    states, inputs = [], []
    cur, inp, mode = {}, {}, None
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        if re.match(r'\s*-> State: \d+\.\d+ <-', line):
            if mode == 'input':
                inputs.append(dict(inp))
            mode = 'state'
            continue
        if re.match(r'\s*-> Input: \d+\.\d+ <-', line):
            states.append(dict(cur))
            mode = 'input'
            continue
        m = re.match(r'\s+(\w+) = (\S+)$', line)
        if m and mode:
            (cur if mode == 'state' else inp)[m.group(1)] = m.group(2)
    if mode == 'state':
        states.append(dict(cur))
    return states, inputs
