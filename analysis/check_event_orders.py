"""Check the event-order abstraction of Section IV-C.

1. The order constraints stated in the paper admit exactly the orders of the
   six second-half election events that are feasible under the day windows
   (Table VIII); events on the same day may be processed in either order.
2. The post_order table of the model (post_order = 1..27) assigns the six
   events distinct positions 1..6 for every value and encodes exactly these
   feasible orders, so no execution can stall in PH_WAIT."""
import itertools, re
from tracelib import read_model_text

# day windows (days after game start). C09 = E-C09/E-C10, X01 = E-DEM01/E-SWR01,
# X02 = E-DEM02/E-SWR02
W = {'C06': (55, 61), 'C07': (70, 90), 'C08': (80, 85),
     'C09': (55, 55), 'X01': (60, 90), 'X02': (75, 75)}

def realizable(order):
    """Greedy day assignment; fails iff no non-decreasing assignment exists."""
    day = 0
    for e in order:
        day = max(day, W[e][0])
        if day > W[e][1]:
            return False
    return True

feasible = {o for o in itertools.permutations(W) if realizable(o)}
cons = [('C09', x) for x in ('C07', 'C08', 'X01', 'X02')] \
     + [('C06', x) for x in ('C07', 'C08', 'X02')] + [('X02', 'C08')]
admitted = {o for o in itertools.permutations(W) if all(o.index(a) < o.index(b) for a, b in cons)}
print(f'1. feasible orders: {len(feasible)}, admitted by the constraints: {len(admitted)}, '
      f'equal: {feasible == admitted}')

src = read_model_text()
names = {'post_rank_work_creation': 'C06', 'post_rank_dirksen_followup': 'C09',
         'post_rank_route_event': 'X01', 'post_rank_union': 'X02',
         'post_rank_berlin': 'C07', 'post_rank_ecumenism': 'C08'}
rank = {}
for d, ev in names.items():
    body = re.search(d + r'\s*:=\s*case(.*?)esac;', src, re.S).group(1)
    tab = {}
    for sets, r in re.findall(r'post_order in \{([\d,\s]+)\}\s*:\s*(\d+);', body):
        for o in map(int, sets.split(',')):
            tab.setdefault(o, int(r))
    default = int(re.search(r'TRUE\s*:\s*(\d+);', body).group(1))
    rank[ev] = {o: tab.get(o, default) for o in range(1, 28)}
encoded, perm_ok = set(), True
for o in range(1, 28):
    rs = {ev: rank[ev][o] for ev in W}
    if sorted(rs.values()) != list(range(1, 7)):
        print(f'   post_order {o} is not a permutation: {rs}'); perm_ok = False; continue
    encoded.add(tuple(sorted(W, key=lambda e: rs[e])))
print(f'2. every post_order is a permutation: {perm_ok}, distinct orders: {len(encoded)}, '
      f'equal to the feasible orders: {encoded == feasible}')
