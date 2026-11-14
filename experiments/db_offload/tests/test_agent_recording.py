"""A fake transport tests trace integrity; it is never generative-agent evidence."""
import io,json,sys
from experiments.db_offload.recovery import agent

def test_requests_keep_the_messages_actually_sent(tmp_path,monkeypatch):
 task={'id':'recording-test','partition':'heldout','query':'What is known?'}
 monkeypatch.setattr(agent,'load',lambda:({},[task],{'seed':1,'budget_bytes':16000,'budget_chars':12000}))
 sent=[]
 def fake_urlopen(request,timeout):
  body=json.loads(request.data);sent.append(body)
  if len(body['messages'])==2:message={'role':'assistant','content':None,'tool_calls':[{'id':'read-1','type':'function','function':{'name':'retrieve','arguments':'{"query":"known evidence"}'}}]}
  else:message={'role':'assistant','content':'Fake fixture output; not a model trial.'}
  return io.BytesIO(json.dumps({'choices':[{'message':message}],'usage':{'total_tokens':1},'cost':{'amount':0,'currency':'fixture-only'}}).encode())
 monkeypatch.setattr(agent.urllib.request,'urlopen',fake_urlopen)
 packets=tmp_path/'packets.json';packets.write_text(json.dumps({'recording-test':{'flat':'source context','native':'source context'}}))
 monkeypatch.setattr(sys,'argv',['agent','--endpoint','http://127.0.0.1:8000/v1','--model','FAKE-UNIT-TEST','--packets',str(packets),'--output',str(tmp_path/'out')])
 agent.main();rows=[json.loads(x) for x in (tmp_path/'out/trials.jsonl').read_text().splitlines()]
 assert len(rows)==9 and len(sent)==18
 for row in rows:
  requests=[event['request'] for event in row['trace'] if 'request' in event]
  assert [len(request['messages']) for request in requests]==[2,4]
  assert all(message.get('content')!='Fake fixture output; not a model trial.' for request in requests for message in request['messages'])
  assert row['cost']==[{'amount':0,'currency':'fixture-only'}]*2
