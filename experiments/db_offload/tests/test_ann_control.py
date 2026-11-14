"""Real HNSW mechanics for the supplemental control, not semantic quality evidence."""
import numpy as np
from experiments.db_offload.ann_diagnostic import ANNFlat
from experiments.db_offload.adapters import Flat
from experiments.db_offload.data import load,permitted

def test_ann_control_preserves_gate_and_independent_working_sets():
 corpus,tasks,_=load();units=permitted(corpus,tasks[0])[:8];vectors=np.eye(8,384,dtype=np.float32);ann=ANNFlat();exact=Flat();a=ann.prepare(units,vectors,[]);b=exact.prepare(units,vectors,[])
 assert ann.search(a,'zxqneverword',vectors[0],8,.3)==exact.search(b,'zxqneverword',vectors[0],8,.3)
 assert [r['uid'] for r in ann.search(a,'zxqneverword',vectors[0],8,.3)]==[units[0]['id']]
 other=ann.prepare(units[1:2],vectors[1:2],[])
 assert other!=a and ann.search(other,'zxqneverword',vectors[0],8,.3)==[]
 assert [r['uid'] for r in ann.search(a,'zxqneverword',vectors[0],8,.3)]==[units[0]['id']]
