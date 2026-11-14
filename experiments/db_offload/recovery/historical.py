"""Unchanged weighted baseline with bounded execution threads; no ranking changes."""
import argparse,asyncio,json
from pathlib import Path
import onnxruntime as ort
from writ_retrieval.evaluation.full_corpus import evaluate
from writ_retrieval.evaluation.compare import paired,read
def main():
 p=argparse.ArgumentParser();p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False);original=ort.InferenceSession
 def bounded(*args,**kwargs):
  options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;return original(*args,sess_options=options,**kwargs)
 ort.InferenceSession=bounded
 asyncio.run(evaluate(argparse.Namespace(store=a.work/'graph',fixtures=Path('tests/fixtures'),model_dir=a.model_dir,cache=a.work/'indexes',output=a.output,label='hosted-replication-original-weights',budget=2000,repeats=1)))
 result={arm:paired(read(Path('evidence/phase2')/(arm+'.jsonl')),read(a.output/(arm+'.jsonl'))) for arm in ('lexical','vector','hybrid_no_graph','hybrid_graph')};(a.output/'comparison.json').write_text(json.dumps({'outputs':1012,'changed':sum(len(r['changed_outputs']) for r in result.values()),'arms':result,'note':'Only timing excluded. Thread limits and repeat counts differ; no latency parity claim.'},indent=2))
if __name__=='__main__':main()
