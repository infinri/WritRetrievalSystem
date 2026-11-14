"""Offline model subprocess; networking remains denied, including in server trials."""
import argparse,json,sys,time
from writ_retrieval.reliable.cli import encoder

def main():
 p=argparse.ArgumentParser();p.add_argument('--model-dir',required=True);a=p.parse_args()
 import onnxruntime as ort
 original=ort.InferenceSession
 def bounded_session(*args,**kwargs):
  options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
  return original(*args,sess_options=options,**kwargs)
 ort.InferenceSession=bounded_session
 start=time.perf_counter();model,identity=encoder(a.model_dir);ort.InferenceSession=original;print(json.dumps({'ready':True,'encoder_id':identity,'startup_ms':(time.perf_counter()-start)*1000}),flush=True)
 for line in sys.stdin:
  request=json.loads(line);start=time.perf_counter()
  vectors=[]
  for offset in range(0,len(request['texts']),16):vectors.extend(model.encode_batch(request['texts'][offset:offset+16]))
  print(json.dumps({'vectors':vectors,'inference_ms':(time.perf_counter()-start)*1000}),flush=True)
if __name__=='__main__':main()
