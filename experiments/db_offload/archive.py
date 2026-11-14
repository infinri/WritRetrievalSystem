"""Lossless deterministic compression of repetitive raw experiment traces."""
import argparse,gzip,hashlib,json
from pathlib import Path

def archive(root):
 records=[]
 for p in sorted(root.rglob('*')):
  if not p.is_file() or not (p.name.endswith('.jsonl') or p.name.endswith('-queries.json')) or p.stat().st_size<100000:continue
  raw=p.read_bytes();target=p.with_suffix(p.suffix+'.gz');target.write_bytes(gzip.compress(raw,mtime=0));p.unlink()
  records.append({'file':str(target.relative_to(root)),'uncompressed_sha256':hashlib.sha256(raw).hexdigest(),'uncompressed_bytes':len(raw),'compressed_sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
 if records:(root/'compression.json').write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);archive(p.parse_args().directory)
