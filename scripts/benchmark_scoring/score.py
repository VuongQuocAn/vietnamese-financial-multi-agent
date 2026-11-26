"""Aggregate locked-review judgments; no API/runtime imports. Run with Python 3.11+."""
import csv, hashlib, json, math, statistics, collections
from pathlib import Path
from decimal import Decimal as D
O=Path(__file__).resolve().parent
P=O.parent/'EO-FROZEN-BENCHMARK-600'
def read(n): return json.loads((O/n).read_text(encoding='utf-8-sig'))
def save(n,x): (O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def csvread(n):
    with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def csvwrite(n,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    def cell(v):return json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v
    with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows({k:cell(v) for k,v in r.items()} for r in rows)
def div(a,b):return a/b if b else 0
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
packet=read('review-packet.json'); locked={r['id']:r for r in read('official-output-map.json')}
sh=read('sh-manual.json'); nr=read('nr-scoring.json'); nm=read('nr-manual.json'); mh=read('mh-manual.json')
oldpilot={r['id']:r for r in read('pilot-baseline-scores.json')}
req=csvread('usage-requests.csv'); uq={r['id']:r for r in csvread('usage-by-qa.csv')}; tq={r['id']:r for r in csvread('timing-by-qa.csv')}
rs=collections.defaultdict(list)
for r in req:rs[r['id']].append(r)
assert len(locked)==len(uq)==len(tq)==len(packet)==600 and len(req)==2210
assert len({r['raw_request'] for r in req})==len(req)
assert collections.Counter(r['type'] for r in packet)=={'SH':200,'MH':200,'NR':200}
assert len(mh)==200 and len(nr)==200 and len(nm)==103 and len(sh)==51
# Explicit recovery categories based on first/last candidates and actual released claims.
technical={'VFB-SH-0001':'Source alias BBS_2025 replaced by T2; first binding empty, second supported, same correct answer.',
'VFB-SH-0061':'EO 123 replaced by EO 1; first bound list empty, second bound F123, unchanged correct value.',
'VFB-NR-0070':'P1 correct but rejected for same-filing comparison; P2 uses equivalent note from AME_2025, accepted. Same correct value, no content improvement.'}
proof_only={'VFB-NR-0085':'P3 correct after retrieval, still blocked.', 'VFB-NR-0109':'P2 correct after wrong P1, still blocked.'}
# Recovery prevents a claim only if actual trace indicates a rejected incorrect candidate.
rows=[]; keys=[]; units=[]; recovery=[]; reviews=[]; changes=[]; usage=[]
for x in packet:
    i=x['id']; t=x['type']; cohort=x['cohort']; final=x['final']; old=x['old']; cs=x['claims']; pr=x['proofs']
    assert locked[i]['path']==x['path'] and locked[i]['cohort']==cohort
    rawpath=P/x['path']; rawbytes=rawpath.read_bytes()
    assert hashlib.sha256(rawbytes).hexdigest()==locked[i]['sha256'],i
    raw=json.loads(rawbytes); secs=raw.get('seconds')
    row=dict(id=i,type=t,cohort=cohort,route=x['route'],runtime_status=x['status'],blocked=int(x['status']=='blocked'),final_empty=int(not final),question=x['question'],gold=x['gold']['display'],gold_type=x['gold']['type'],gold_unit=x['gold']['unit'],final=final,trace=x['path'],sha256=locked[i]['sha256'],recovery_rounds=x['recovery'],published_proof_ids=x['published_proofs'],proof_ids=[p['id'] for p in pr],e2e_seconds=secs)
    if t=='SH':
        s=sh.get(i,old); assert 'final_content_correct' in s
        row.update({k:s.get(k,0) for k in ['candidate_correct','final_content_correct','grounded_full','recovery_rescued_final','wrong_candidate_prevented']})
        row.update(content_correct=int(s['final_content_correct']),correct_candidate_lost=int(s['candidate_correct'] and not s['final_content_correct']),wrong_or_incomplete_published=int(bool(final) and not s['final_content_correct']),false_final=int(s.get('false_factual_published',bool(final) and not s['final_content_correct'])),claim_source_rate=int(s['grounded_full']),gold_grounded_rate=int(s['grounded_full']),first_failure=s.get('first_failure'),note=s.get('note',''),grading_method='typed exact / manual semantic and citation check')
    elif t=='NR':
        s=dict(nr[i]); manual=nm.get(i)
        if manual:
            assert len(manual['proofs'])==len(s['proof_checks']),i
            for c,b in zip(s['proof_checks'],manual['proofs']):
                c['business']=bool(b);c['manual_note']=manual['note']
            for k in ['first_failure','note','recovery_rescued_final','wrong_candidate_prevented']:s[k]=manual[k]
        assert all(c['business'] is not None for c in s['proof_checks']),i
        s['proof_correct_first']=int(bool(s['proof_checks']) and s['proof_checks'][0]['business'])
        s['proof_correct_initial_candidate']=int(any(c['business'] and any(b.get('proof')==c['proof_id'] for b in (x['candidates'][0]['bound'] if x['candidates'] else [])) for c in s['proof_checks']))
        s['proof_correct_any']=int(any(c['business'] for c in s['proof_checks']))
        s['proof_correct_to_final']=int(any(c['business'] and c['proof_id'] in x['published_proofs'] for c in s['proof_checks']))
        s['grounded_full']=int(s['final_value_unit_correct'] and s['proof_correct_to_final'])
        s['wrong_business_published']=int(bool(final) and not s['proof_correct_to_final'])
        row.update(s);row.update(content_correct=s['final_value_correct'],false_final=int(bool(final) and (not s['final_value_unit_correct'] or not s['proof_correct_to_final'])),claim_source_rate=s['grounded_full'],gold_grounded_rate=s['grounded_full'],wrong_or_incomplete_published=int(bool(final) and not s['final_value_correct']))
    else:
        s=mh[i]; goldkeys=x['gold']['key_points'] or [x['gold']['display']]
        mapped={k['key']:k for k in s['key_matches']}
        assert len(mapped)==len(s['key_matches'])
        for j,key in enumerate(goldkeys,1):
            m=mapped.get(j,{}); ids=m.get('claims',[])
            citations=[dict(claim=c,citations=cs[c-1]['citations']) for c in ids]
            keys.append(dict(id=i,cohort=cohort,key_index=j,gold_key=key,correct=int(bool(m)),grounded=int(m.get('grounded',False)),matched_claim_indices=ids,matched_claims=[cs[c-1]['answer'] for c in ids],claim_linked_citations=citations,note=s['note'],trace=x['path']))
        for j,u in enumerate(s['claim_units'],1):
            c=cs[u['claim']-1];units.append(dict(id=i,cohort=cohort,unit_index=j,raw_claim_index=u['claim'],claim=c['answer'],gold_confirmed=u['gold_confirmed'],grounded=u['grounded'],false=u['false'],citations=c['citations'],note=s['note']))
        n=len(s['claim_units']); confirmed=sum(u['gold_confirmed'] for u in s['claim_units']); grounded=sum(u['grounded'] for u in s['claim_units']); kg=sum(k['grounded'] for k in mapped.values())
        prec=div(confirmed,n); rec=div(len(mapped),len(goldkeys))
        assert not s['full'] or len(mapped)==len(goldkeys),i
        assert not s['grounded_full'] or (s['strict_full'] and kg==len(goldkeys) and grounded==n),i
        row.update({k:v for k,v in s.items() if k not in ('claim_units','key_matches')})
        row.update(content_correct=s['full'],gold_keypoint_count=len(goldkeys),correct_gold_count=len(mapped),grounded_gold_count=kg,correct_gold=sorted(mapped),grounded_gold=sorted(k for k,v in mapped.items() if v['grounded']),published_claim_count=n,gold_confirmed_claim_count=confirmed,grounded_claim_count=grounded,claim_precision=prec,claim_recall=rec,claim_f1=div(2*prec*rec,prec+rec),claim_source_rate=div(grounded,n),gold_grounded_rate=div(kg,len(goldkeys)),false_final=int(any(u['false'] for u in s['claim_units'])),wrong_or_incomplete_published=int(bool(final) and not s['full']))
        row['grading_method']='manual claim/keypoint assessment; unique units; linked citation only'
        if pr: row.update(mh_proof_generated=1,mh_proof_right_task=0,mh_proof_wrong_published=int(bool(x['published_proofs'])))
    # Trace-level source/proof uncertainty kept separate from content.
    row['review_required']=int((row['content_correct'] and not row['grounded_full']) or (t=='MH' and row.get('correct_gold_count',0)>row.get('grounded_gold_count',0)) or (t=='NR' and i in nm and any(c.get('manual_note') for c in row['proof_checks']) and row['proof_correct_any'] and not row['proof_correct_to_final']) or i in ('VFB-NR-0187','VFB-NR-0193'))
    if row['review_required']:reviews.append(dict(id=i,type=t,cohort=cohort,reason=row['note'] or 'Đúng nội dung nhưng chưa đủ nguồn/proof; kiểm tra trace.',trace=x['path']))
    row['recovery_category']='none'
    if x['recovery']:
        if row.get('recovery_rescued_final'): cat='content_rescue'
        elif i in technical:cat='technical_handoff_rescue'
        elif i in proof_only:cat='proof_only_no_final'
        elif row.get('recovery_partial'):cat='partial_new_gold_key'
        elif row.get('wrong_candidate_prevented'):cat='wrong_claim_or_proof_prevented'
        elif row['grounded_full']:cat='already_correct_no_rescue'
        else:cat='no_confirmed_improvement'
        row['recovery_category']=cat
        recovery.append(dict(id=i,type=t,cohort=cohort,category=cat,first_candidate=x['candidates'][0] if x['candidates'] else None,last_candidate=x['candidates'][-1] if x['candidates'] else None,final=final,proof_checks=row.get('proof_checks'),verdicts=x['verification'],note=technical.get(i,proof_only.get(i,row['note'])),trace=x['path']))
    # Usage is deduplicated by raw request path; unknown tokens/seconds are not imputed.
    rr=rs[i]; u=uq[i]; tm=tq[i]
    for k in ('input_tokens','cached_input_tokens','output_tokens','total_tokens','cost_usd','unknown_upper_usd'):
        assert sum((D(z[k]) for z in rr if z[k] not in ('','None','null','unknown')),D(0))==D(u[k]),(i,k)
    assert len(rr)==int(u['requests'])
    api_missing=sum(z['seconds'] in ('','None','null','unknown') for z in rr); api_known=sum((D(z['seconds']) for z in rr if z['seconds'] not in ('','None','null','unknown')),D(0))
    # Time sum of per-request observations; if incomplete, keep exact total blank.
    ur=dict(u,official_e2e_seconds=secs,qa_attempts=tm['qa_attempts'],e2e_all_attempts_seconds_known=tm['qa_seconds_known'],e2e_all_attempts_seconds='' if int(tm['qa_attempts_unknown_time']) else tm['qa_seconds_known'],e2e_missing_attempts=tm['qa_attempts_unknown_time'],api_seconds_known=str(api_known),api_seconds_total='' if api_missing else str(api_known),api_missing_requests=api_missing,missing_reason=('Unknown response usage for '+str(u['unknown_usage_requests'])+' request(s). ' if int(u['unknown_usage_requests']) else '')+('An interrupted attempt has no elapsed time. ' if int(tm['qa_attempts_unknown_time']) else '')+('Request duration unavailable. ' if api_missing else ''))
    usage.append(ur)
    row.update({k:ur[k] for k in ('requests','unknown_usage_requests','input_tokens','cached_input_tokens','output_tokens','total_tokens','cost_usd','unknown_upper_usd','api_seconds_known','api_seconds_total','api_missing_requests','e2e_missing_attempts','missing_reason')})
    row['first_failure']=str(row.get('first_failure') or 'None').lower()
    if i in oldpilot:
        op=oldpilot[i]
        fields={'SH':['final_content_correct','grounded_full','candidate_correct','correct_candidate_lost'],'NR':['final_value_correct','final_unit_correct','final_value_unit_correct','grounded_full','proof_correct_first','proof_correct_to_final'],'MH':['full','strict_full','grounded_full','correct_gold_count','grounded_gold_count','published_claim_count','gold_confirmed_claim_count','claim_f1','false_final']}[t]
        for k in fields:
            if k in op and k in row and (abs(op[k]-row[k])>1e-9 if isinstance(op[k],(int,float)) else op[k]!=row[k]):
                changes.append(dict(id=i,type=t,metric=k,old=op[k],new=row[k],reason=row['note']))
    rows.append(row)
assert len(rows)==600 and len(keys)>0
def summ(sub):
    n=len(sub); assert n
    def cnt(k):return sum(int(r.get(k,0) or 0) for r in sub)
    def avg(k):return sum(float(r.get(k,0) or 0) for r in sub)/n
    times=sorted(float(r['e2e_seconds']) for r in sub if r['e2e_seconds'] is not None)
    tt=collections.Counter(r['type'] for r in sub)
    m=dict(n=n,content_correct=cnt('content_correct'),grounded_full=cnt('grounded_full'),blocked=cnt('blocked'),final_empty=cnt('final_empty'),false_final=cnt('false_final'),wrong_or_incomplete_published=cnt('wrong_or_incomplete_published'),recovery_qa=sum(bool(r['recovery_rounds']) for r in sub),recovery_categories=dict(collections.Counter(r['recovery_category'] for r in sub if r['recovery_rounds'])),review_required=cnt('review_required'),route_other=sum(r['route']!=r['type'] for r in sub),first_failures=dict(collections.Counter(r['first_failure'] for r in sub if not r['grounded_full'])),claim_source_rate_mean=avg('claim_source_rate'),gold_grounded_rate_mean=avg('gold_grounded_rate'),e2e_n=len(times),e2e_median_s=statistics.median(times),e2e_p95_s=times[math.ceil(.95*len(times))-1],e2e_sum_s=sum(times),api_seconds_known=str(sum(D(r['api_seconds_known']) for r in sub)),unknown_request_time=cnt('api_missing_requests'),unknown_attempt_time=cnt('e2e_missing_attempts'))
    for k in ['input_tokens','cached_input_tokens','output_tokens','total_tokens','requests','unknown_usage_requests']:m[k]=cnt(k)
    for k in ['cost_usd','unknown_upper_usd']:m[k]=str(sum(D(r[k]) for r in sub))
    if len(tt)==1:
        t=next(iter(tt))
        if t=='SH':
            for k in ['candidate_correct','correct_candidate_lost']:m[k]=cnt(k)
            m['correct_content_wrong_or_missing_source']=m['content_correct']-m['grounded_full']
        elif t=='NR':
            for k in ['final_value_correct','final_unit_correct','final_value_unit_correct','rounding_tolerance','proof_generated','proof_correct_first','proof_correct_initial_candidate','proof_correct_any','proof_correct_to_final','wrong_value_published','wrong_business_published']:m[k]=cnt(k)
        else:
            for k in ['full','strict_full','correct_gold_count','grounded_gold_count','gold_keypoint_count','published_claim_count','gold_confirmed_claim_count','grounded_claim_count','mh_proof_generated','mh_proof_wrong_published']:m[k]=cnt(k)
            for k in ['claim_precision','claim_recall','claim_f1']:m[k+'_mean']=avg(k)
            m['gold_correct_micro']=div(m['correct_gold_count'],m['gold_keypoint_count']);m['gold_grounded_micro']=div(m['grounded_gold_count'],m['gold_keypoint_count'])
    return m
metrics={}
for name in ('pilot90','remaining510','all600'):
    sub=[r for r in rows if name=='all600' or r['cohort']==name]
    metrics[name]={t:summ([r for r in sub if t=='ALL' or r['type']==t]) for t in ['SH','MH','NR','ALL']}
    original=read('usage-summary.json')[name]
    for t,m in metrics[name].items():
        for k in ('input_tokens','cached_input_tokens','output_tokens','total_tokens','requests','unknown_usage_requests','cost_usd','unknown_upper_usd'):
            assert D(m[k])==D(original[t][k]),(name,t,k,m[k],original[t][k])
metrics['rubric_sha256']=sha(O/'Huong_dan_cham_diem_SH_NR_MH.md')
metrics['new_api_cost_usd']='0';metrics['rag_comparison']={t:dict(rag_correct=v,eo_correct=metrics['all600'][t]['content_correct'],delta_count=metrics['all600'][t]['content_correct']-v,delta_pp=(metrics['all600'][t]['content_correct']-v)/2) for t,v in [('SH',169),('MH',47),('NR',50)]}
metrics['pilot_metric_changes']=len(changes);metrics['review_count']=len(reviews)
clean_requests=[]
for r in req:
    missing=[k for k,v in r.items() if v in ('unknown','None','null')]
    clean_requests.append(dict({k:('' if k in missing else v) for k,v in r.items()},missing_reason='Provider response/usage or timing unavailable: '+', '.join(missing) if missing else ''))
csvwrite('usage-requests-normalized.csv',clean_requests)
csvwrite('qa-scores.csv',rows);save('evaluation.json',rows);csvwrite('mh-claim-mapping.csv',keys);csvwrite('mh-final-claim-units.csv',units);csvwrite('recovery-audit.csv',recovery);csvwrite('review-queue.csv',reviews);csvwrite('pilot-rescore-diff.csv',changes);csvwrite('usage-and-timing-by-qa.csv',usage);save('metrics.json',metrics)
print(json.dumps(metrics['all600'],ensure_ascii=False,indent=2));print('pilot-diff',len(changes),'review',len(reviews),'gold-keys',len(keys),'claim-units',len(units))
