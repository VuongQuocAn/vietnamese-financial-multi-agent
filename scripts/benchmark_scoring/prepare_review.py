import json,collections,pathlib,hashlib,re,sys
from decimal import Decimal as D
O=pathlib.Path(__file__).resolve().parent; P=O.with_name('EO-FROZEN-BENCHMARK-600'); M=O.parents[2]
def read(p):return json.loads(p.read_bytes())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def compact():
    paths=read(O/'official-output-map.json'); original={r['id']:r for r in read(P/'evaluation.json')}
    gold={}
    for folder in ('single_hop','multi_hop','numerical'):
        for line in (M/'ViFinBench/benchmark'/folder/'full.jsonl').read_text(encoding='utf8').splitlines():
            g=json.loads(line);gold[g['id']]=g
    assert set(gold)==set(original)=={r['id'] for r in paths}
    out=[]
    for x in paths:
        r=read(P/x['path']);g=gold[x['id']];e=original[x['id']]
        targets=[s['target'] for s in e.get('source_checks',[])]
        # Gold targets retain source coords and quote; raw source values in original trace.
        refs=[]
        for ob in r.get('obligations',[]):
            for c in ob.get('verified_claims',[]):
                cs=[]
                for s in c.get('sources',[]):
                    q=s['citation']; val=q.get('source_value')
                    cs.append(dict(id=q['id'],filing=q['filing'],page=q['page'],pointer=q['pointer'],value=val,title=s.get('title'),row=s.get('row'),columns=s.get('columns')))
                refs.append(dict(answer=c['answer'],citations=cs))
        candidates=[]
        for c in r.get('candidates',[]):
            candidates.append(dict(raw=c.get('raw'),bound=[dict(answer=b.get('answer'),issue=b.get('issue'),proof=b.get('proof')) for b in c.get('bound',[])],assessment=c.get('assessment')))
        proof=[]
        for pr in r.get('calculator_proofs',[]):
            proof.append({**{k:pr.get(k) for k in ('id','display','value','unit','exact','decimals','expression')},'operands':{k:{a:v.get(a) for a in ('label','period','column','raw','value','scale','unit','group','filing','page','pointer','title')} for k,v in pr['operands'].items()}})
        out.append({**x,'question':g['question'],'gold':g['answer'],'formula':g.get('formula'),'operands':g.get('operands'),'targets':targets,'visible':[(s['initial'],s['ever']) for s in e.get('source_checks',[])],'final':r.get('answer'),'route':r.get('route'),'claims':refs,'candidates':candidates,'proofs':proof,'published_proofs':r.get('published_proofs',[]),'recovery':r.get('recovery_rounds',0),'verification':[(z.get('status'),z.get('issue')) for z in r.get('events',[]) if z.get('event')=='verification'],'old':{k:v for k,v in e.items() if k not in ('source_checks','proofs','citations','candidate_raw','final','gold','question','published_proofs')}})
    save(O/'review-packet.json',out)
    print('review packets',len(out))
if __name__=='__main__':compact()
