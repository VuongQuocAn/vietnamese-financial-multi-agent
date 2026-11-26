import json,pathlib,sys
from prepare_review import O,read,save
p=O/'mh-manual.json';j=read(p) if p.exists() else {}
# compact input: id, key-to-claim mapping (key:claim+claim:G|U), units (claim:CGF), full, strict, GF, first failure, note, rescue, prevented, partial
for n,m,u,f,s,g,c,note,*extra in json.loads(sys.stdin.read().lstrip("\uFEFF")):
    id=f'VFB-MH-{n:04d}'
    keys=[]
    for token in m.split():
        k,cs,b=token.split(':');keys.append(dict(key=int(k),claims=[int(x) for x in cs.split('+')],grounded=b=='G'))
    claims=[]
    for token in u.split():
        ci,flags=token.split(':');claims.append(dict(claim=int(ci),gold_confirmed=int(flags[0]),grounded=int(flags[1]),false=int(flags[2])))
    j[id]=dict(key_matches=keys,claim_units=claims,full=f,strict_full=s,grounded_full=g,first_failure=c,note=note,recovery_rescued_final=bool(extra[0]) if extra else False,wrong_candidate_prevented=int(extra[1]) if len(extra)>1 else 0,recovery_partial=int(extra[2]) if len(extra)>2 else 0)
save(p,j);print('MH reviewed',len(j))
