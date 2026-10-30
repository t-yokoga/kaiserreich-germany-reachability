"""Check that the tightened upper bounds of the seat variables in the model are
conservative. For each route (E-C01 option), the largest possible increase is
the sum of the three largest decision increments of that route plus, for every
event, its largest increment, taking only one event of each mutually exclusive
pair (E-C09/E-C10; route-specific events follow the route). Decreases are ignored."""
import re
from tracelib import read_model_text
src=read_model_text()
decl={m.group(1):int(m.group(2)) for m in re.finditer(r'(seats_\w+)\s*:\s*0\.\.(\d+);',src)}
init={m.group(1):int(m.group(2)) for m in re.finditer(r'init\((seats_\w+)\)\s*:=\s*(\d+);',src)}
DEM_DEC={'SAXON','SOCIALIST','JOINT','DEMOCRATIC','SEL_ZEN'}; SWR_DEC={'HESSE','DKPDVLP','ENDORSE_ZEN','COOPERATE','CHALLENGE'}
DEM_EV={'PH_EV_SILESIA','PH_EV_DEMUNION'}; SWR_EV={'PH_EV_PROPAGANDA','PH_EV_BWR_FRONT'}
ok_all=True
for v in ['seats_far_left','seats_spd','seats_lvp','seats_guelph','seats_minor_lib','seats_minority','seats_zentrum','seats_agrarian','seats_dkp','seats_dvlp','seats_far_right']:
    body=re.search(r'next\('+v+r'\)\s*:=\s*case(.*?)esac;',src,re.S).group(1)
    dec={}; ev={}
    for line in body.split(';'):
        if ':' not in line: continue
        guard,rhs=line.split(':',1)
        m=re.search(v+r'\s*\+\s*(\d+)',rhs)
        if m: inc=int(m.group(1))
        elif re.search(v+r'\s*\+\s*\(seats_guelph - 1\)',rhs): inc=3   # Federalist opt.2 with 0<guelph<5
        else: continue
        if 'PH_DECISION' in guard:
            d=re.search(r'dec_choice\s*=\s*(\w+)',guard).group(1); dec[d]=max(dec.get(d,0),inc)
        else:
            ph=re.search(r'phase\s*=\s*(\w+)',guard).group(1); ev[ph]=max(ev.get(ph,0),inc)
    best=0
    for rd,rev_own,rev_other in [(DEM_DEC,DEM_EV,SWR_EV),(SWR_DEC,SWR_EV,DEM_EV)]:
        d=sum(sorted([dec.get(k,0) for k in rd],reverse=True)[:3])
        e={p:i for p,i in ev.items() if p not in rev_other}
        dm=max(e.pop('PH_EV_DEADLOCK',0),e.pop('PH_EV_MARCH_FALLS',0))
        best=max(best,d+sum(e.values())+dm)
    ub=init[v]+best; ok=decl[v]>=ub; ok_all&=ok
    print(f'{v:18s} init {init[v]:3d}  declared max {decl[v]:3d}  route-aware worst case {ub:3d}  {"OK" if ok else "TOO SMALL"}')
print('all bounds conservative:',ok_all)

# Upper bound of seats_schleicher_block (declared 0..53): N-SHF02 moves 15% of
# DVLP, N-C06 moves 20% of DVLP, 10% of SPD and 10% of DkP; each NF at most once.
def route_max(v, route):
    body=re.search(r'next\('+v+r'\)\s*:=\s*case(.*?)esac;',src,re.S).group(1)
    dec={}; ev={}
    for line in body.split(';'):
        if ':' not in line: continue
        guard,rhs=line.split(':',1)
        m=re.search(v+r'\s*\+\s*(\d+)',rhs)
        if m: inc=int(m.group(1))
        elif re.search(v+r'\s*\+\s*\(seats_guelph - 1\)',rhs): inc=3
        else: continue
        if 'PH_DECISION' in guard:
            d=re.search(r'dec_choice\s*=\s*(\w+)',guard).group(1); dec[d]=max(dec.get(d,0),inc)
        else:
            ph=re.search(r'phase\s*=\s*(\w+)',guard).group(1); ev[ph]=max(ev.get(ph,0),inc)
    rd,own,other=(DEM_DEC,DEM_EV,SWR_EV) if route=='DEM' else (SWR_DEC,SWR_EV,DEM_EV)
    d=sum(sorted([dec.get(k,0) for k in rd],reverse=True)[:3])
    e={p:i for p,i in ev.items() if p not in other}
    dm=max(e.pop('PH_EV_DEADLOCK',0),e.pop('PH_EV_MARCH_FALLS',0))
    return init[v]+d+sum(e.values())+dm
best=0
for route in ('DEM','SWR'):
    dv,sp,dk=(route_max(x,route) for x in ('seats_dvlp','seats_spd','seats_dkp'))
    a=dv*15//100; b=(dv-a)*20//100 + sp*10//100 + dk*10//100        # N-SHF02 then N-C06
    c=dv*20//100 + sp*10//100 + dk*10//100; d=(dv-dv*20//100)*15//100  # N-C06 then N-SHF02
    best=max(best,a+b,c+d)
    print(f'route {route}: DVLP<={dv} SPD<={sp} DkP<={dk} -> Schleicher bloc <= {max(a+b,c+d)}')
print('seats_schleicher_block declared max', decl['seats_schleicher_block'], 'OK' if decl['seats_schleicher_block']>=best else 'TOO SMALL')
