"""Model size and an approximation of the cone of influence (Sections IV-G, V).

Size: number of state/input variables and Boolean bits under a logarithmic
encoding. Cone: static closure of the variables of each LTLSPEC over the next()
assignments, DEFINE expansion, and the TRANS constraint (treated as one
constraint, as nuXmv does for a single TRANS)."""
import math, re
from tracelib import read_model_text

src = read_model_text()
sec = lambda a, b: re.search(r'\n' + a + r'\s*\n(.*?)\n' + b, src, re.S).group(1)

def decls(txt):
    out = []
    for m in re.finditer(r'(\w+)\s*:\s*(\{[^}]*\}|\d+\.\.\d+|boolean)\s*;', txt, re.S):
        n, t = m.groups()
        if t == 'boolean': k = 2
        elif t.startswith('{'): k = len([x for x in t.strip('{}').split(',') if x.strip()])
        else: a, b = map(int, t.split('..')); k = b - a + 1
        out.append((n, k))
    return out

V, IV = decls(sec('VAR', 'IVAR')), decls(sec('IVAR', 'ASSIGN'))
bits = lambda L: sum(max(1, math.ceil(math.log2(k))) for _, k in L)
print(f'state variables: {len(V)} ({bits(V)} bits); input variables: {len(IV)} ({bits(IV)} bits)')

Vn = [n for n, _ in V]
assign = re.search(r'\nASSIGN(.*?)\nDEFINE', src, re.S).group(1)
define = re.search(r'\nDEFINE(.*?)\nTRANS', src, re.S).group(1)
trans = re.search(r'\nTRANS(.*?)(?:\nLTLSPEC|\nCTLSPEC|\Z)', src, re.S).group(1)
defs = {m.group(1): m.group(2) for m in
        re.finditer(r'(\w+)\s*:=\s*(.*?);(?=\s*\w+\s*:=|\s*$)', define, re.S)}
ids = lambda s: set(re.findall(r'[A-Za-z_]\w*', s))

def expand(names, seen=None):
    seen = seen if seen is not None else set(); out = set()
    for n in names:
        if n in defs and n not in seen:
            seen.add(n); out |= expand(ids(defs[n]), seen)
        elif n in Vn:
            out.add(n)
    return out

nexts = {m.group(1): expand(ids(m.group(2))) for m in
         re.finditer(r'next\((\w+)\)\s*:=(.*?);\s*(?=next\(|init\(|$)', assign, re.S)}
trans_vars = expand(ids(trans))

def cone(vs):
    c, work, used = set(vs), list(vs), False
    while work:
        v = work.pop(); dep = set(nexts.get(v, set()))
        if not used and v in trans_vars:
            dep |= trans_vars; used = True
        for d in dep - c:
            c.add(d); work.append(d)
    return c

for name, formula in re.findall(r'LTLSPEC\s+NAME\s+(\w+)\s*:=\s*(.*?);', src, re.S):
    c = cone(expand(ids(formula)))
    print(f'{name}: cone {len(c)} of {len(Vn)} state variables; outside: {sorted(set(Vn) - c)}')
