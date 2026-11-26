"""Replay actual CLI through pinned local retrieval; only transport is replaced.
Usage: python replay_cli.py <checkout> <assets> <benchmark-artifact> <output-root> [--question-only]
"""
import hashlib, importlib.util, json, os, pathlib, runpy, sys, time, traceback
import httpx
P=pathlib.Path
root,assets,bench,out=map(lambda x:P(x).resolve(),sys.argv[1:5])
assert root!=assets and out!=root
out.mkdir(parents=True,exist_ok=False)
os.environ["OPENAI_API_KEY"]="offline-replay-key-not-a-real-secret"
os.environ["HF_HUB_OFFLINE"]="1"
name="vietnamese_financial_multi_agent"
# Explicit source package loaded from the tested checkout, never old editable installation.
spec=importlib.util.spec_from_file_location(name,root/'src/__init__.py',submodule_search_locations=[str(root/'src')])
package=importlib.util.module_from_spec(spec);sys.modules[name]=package;spec.loader.exec_module(package)
cli=root/'scripts/run_agent_v2.py'
ids=['VFB-SH-0026','VFB-MH-0054','VFB-NR-0033']
def load(p):return json.loads(p.read_bytes())
samples={}
for i in ids:
 d=bench/'pilot-live'/i; result=load(d/'result.json')
 seq=[(load(req),d/req.name.replace('-request','-response')) for req in sorted(d.glob('*-request.json'))]
 assert all(resp.is_file() for _,resp in seq)
 samples[i]=(result,seq)
audit=[];failures=[]
class ReplayTransport:
 def __init__(self,*a,**kw):self.id=None;self.index=0
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def handle_request(self,request):
  body=json.loads(request.content)
  if str(request.url)!='https://api.openai.com/v1/chat/completions':raise AssertionError('unexpected endpoint')
  if self.id is None:
   matched=[i for i,(_,seq) in samples.items() if seq[0][0]==body]
   if len(matched)!=1:
    differences={i:[k for k in set(body)|set(seq[0][0]) if body.get(k)!=seq[0][0].get(k)] for i,(_,seq) in samples.items()}
    failures.append({'first_request_mismatch':differences});raise AssertionError('no exact first request match')
   self.id=matched[0]
  old,resp=samples[self.id][1][self.index]
  if old!=body:
   fields=[k for k in set(old)|set(body) if old.get(k)!=body.get(k)]
   failures.append({'id':self.id,'request':self.index+1,'different_fields':fields})
   raise AssertionError(f'request body mismatch {self.id} {self.index+1}: {fields}')
  audit.append({'id':self.id,'index':self.index+1,'request_exact':True,'response_sha256':hashlib.sha256(resp.read_bytes()).hexdigest()})
  self.index+=1
  return httpx.Response(200,content=resp.read_bytes(),request=request)
httpx.HTTPTransport=ReplayTransport
rows=[dict(id=i,type=i.split('-')[1],question=samples[i][0]['item']['question']) for i in ids]
manifest=out/'manifest.json';manifest.write_text(json.dumps({'selected':rows},ensure_ascii=False),encoding='utf8')
os.chdir(root)
common=['--assets',str(assets),'--workers','1','--budget','0.10']
results=[]
def run(mode,arguments,expected):
 dest=out/mode
 sys.argv=[str(cli),*arguments,*common,'--output',str(dest)]
 t=time.perf_counter()
 runpy.run_path(str(cli),run_name='__main__')
 for name,i in expected:
  got=load(dest/name/'result.json');old=samples[i][0]
  keys=['route','status','answer','citations','published_proofs','calculator_proofs']
  diff=[k for k in keys if got.get(k)!=old.get(k)]
  # Record exact equality of released Final and attached sources/proofs; timing and trace IDs ignored.
  results.append({'entry':mode,'id':i,'status':got.get('status'),'route':got.get('route'),'different_fields':diff,'seconds':time.perf_counter()-t,'calls':len(got.get('api',[])),'error':got.get('detail')})
  if diff:failures.append({'id':i,'entry':mode,'different_fields':diff})
if '--question-only' not in sys.argv:
 run('manifest',['--manifest',str(manifest)],[(i,i) for i in ids])
run('question',['--question',rows[0]['question']],[('qa',ids[0])])
imports={k:str(P(v.__file__).resolve()) for k,v in sys.modules.items() if (k==name or k.startswith(name+'.')) and getattr(v,'__file__',None)}
assert all(P(v).is_relative_to(root) for v in imports.values())
summary={'results':results,'transport':audit,'failures':failures,'imports':imports,'new_api_calls':0,'new_api_cost_usd':'0'}
(out/'smoke-summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({'results':results,'failures':failures,'replayed_requests':len(audit)},ensure_ascii=False))
if failures:sys.exit(1)
