"""Real Relate plus injected index failure: prior generation remains recoverable."""
import copy
import numpy as np
import pytest
from experiments.db_offload.data import load,permitted,norm
from experiments.db_offload.adapters import Native
def test_failed_replacement_keeps_prior_generation(tmp_path):
 c,t,s=load();u=permitted(c,t[0])[:8];v=norm(np.ones((8,384)));n=Native(tmp_path/'graph',heavy=True);scope=n.prepare(u,v,[]);view=n.views[scope];before=n.search(scope,'source',v[0]);original=n.execute;replacement=copy.deepcopy(u);replacement[0]['source_revision']='failed-new-revision'
 def injected(query,params=None):
  if query.startswith('CREATE FULLTEXT'):raise OSError('injected index construction failure')
  return original(query,params)
 n.execute=injected
 with pytest.raises(OSError):n.prepare(replacement,v,[])
 n.execute=original;assert list(n.views)==[scope];assert n.search(scope,'source',v[0])==before;assert n.execute('MATCH (p:BOPublished) RETURN count(p) AS count')[0]['count']==1;n.close();reopened=Native(tmp_path/'graph',heavy=True);reopened.views[scope]=view;assert reopened.search(scope,'source',v[0])==before;reopened.close()
