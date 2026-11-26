import ast,re,collections,sys
from decimal import Decimal as D
import sympy as sp
from prepare_review import O,read,save
def numeric_unit(unit):
    return {'%':'percent','vnd':'vnd','lần':'ratio','times':'ratio','ngày':'day','điểm phần trăm':'percentage_point','percentage point':'percentage_point','percentage points':'percentage_point','pp':'percentage_point'}.get(str(unit).lower(),str(unit).lower())
def expr(text,symbols):
    def walk(node):
        if isinstance(node,ast.Name):return symbols[node.id]
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):return sp.Rational(str(node.value))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):return walk(node.operand)*(1 if isinstance(node.op,ast.UAdd) else -1)
        if isinstance(node,ast.BinOp):
            a,b=walk(node.left),walk(node.right)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.Div):return a/b
            if isinstance(node.op,ast.Pow):return a**b
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='abs' and len(node.args)==1:return sp.Abs(walk(node.args[0]))
        raise ValueError('unsupported expression')
    return walk(ast.parse(text,mode='eval').body)
def exact_proof(p,pr):
    g=p['gold']; v=D(pr['value']); gv=D(g['value'])
    if v!=gv:return False,'wrong_value'
    if numeric_unit(pr['unit'])!=g['unit']:return False,'wrong_unit'
    gos=p['operands']; ts=p['targets']
    if len(gos)!=len(pr['operands']):return None,'operand_count'
    symbols={x['name']:sp.Symbol(x['name'],real=True,**({'positive':True} if D(x['value'])>0 else {'negative':True} if D(x['value'])<0 else {})) for x in gos}
    # Gold values alone are insufficient; require exact operand address + value.
    mapping={}
    for code,op in pr['operands'].items():
        found=[]
        for x in gos:
            try:t=ts[int(x['evidence_ref'][1:])-1]
            except (IndexError,ValueError,KeyError):continue
            if op['filing']==t['document_id'] and op['page']==t['page'] and op['pointer'] in {q['pointer'] for q in t.get('coordinates',[])} and D(op['value'])==D(x['value']):found.append(x['name'])
        if len(found)!=1:return None,'coordinate_or_value_mismatch'
        mapping[code]=found[0]
    if len(set(mapping.values()))!=len(gos):return None,'operand_binding_ambiguous'
    try:
        a=expr(pr['expression'],{code:symbols[name] for code,name in mapping.items()})
        b=expr(p['formula']['expression'],symbols)
        equal=sp.simplify(a-b)==0
    except Exception:return None,'expression_parse'
    return (True,'exact_operands_and_equivalent_expression') if equal else (None,'non_equivalent_expression')
def assess():
    data=read(O/'review-packet.json'); result={}; review=[]
    for p in data:
        if p['type']!='NR':continue
        id=p['id']; old=p['old']; g=p['gold']; ps=p['proofs']; released=[q for q in ps if q['id'] in p['published_proofs']]
        assert len(released)<=1,(id,released)
        f=released[0] if released else None
        if f:assert f['display'] in p['final'],id
        assert bool(f)==bool(p['final']),id
        v=int(f is not None and D(f['value'])==D(g['value']))
        unit=int(f is not None and numeric_unit(f['unit'])==g['unit'])
        places=p['formula']['rounding']['decimal_places']
        tol=int(f is not None and abs(D(f['value'])-D(g['value']))<=D(10)**(-places))
        checks=[dict(proof_id=pr['id'],business=exact_proof(p,pr)[0],reason=exact_proof(p,pr)[1]) for pr in ps]
        # Preserve prior semantic judgments for exact cases unless conflict; review unknown proof outcomes.
        row=dict(final_value_correct=v,final_unit_correct=unit,final_value_unit_correct=v*unit,rounding_tolerance=tol,proof_generated=int(bool(ps)),proof_count=len(ps),proof_checks=checks,first_failure=old.get('first_failure','None'),note=old.get('note',''),recovery_rescued_final=False,wrong_candidate_prevented=old.get('wrong_candidate_prevented',0),grading_method='exact decimal and symbolic proof/source check')
        initial=checks[0]['business'] if checks else False
        last=next((q['business'] for q in checks if f and q['proof_id']==f['id']),False)
        # Unknowns require a human review even if a previous score exists; old judgment is available.
        if any(x['business'] is None for x in checks):review.append(id)
        row['proof_correct_first']=int(initial is True)
        row['proof_correct_to_final']=int(last is True)
        row['grounded_full']=int(v and unit and last is True)
        row['wrong_value_published']=int(bool(f) and not v)
        row['wrong_business_published']=int(bool(f) and last is not True)
        if row['grounded_full'] and not initial and p['recovery']:review.append(id)
        if not row['grounded_full'] and not old.get('graded'):review.append(id)
        if old.get('graded') and (v!=old.get('final_value_correct') or unit!=old.get('final_unit_correct') or (last is True and not old.get('proof_correct_to_final'))):review.append(id)
        result[id]=row
    save(O/'nr-scoring.json',result);save(O/'nr-review-pending.json',sorted(set(review)))
    print('NR auto',len(result),'review',len(set(review)),collections.Counter(x['reason'] for r in result.values() for x in r['proof_checks']))
if __name__=='__main__':assess()
