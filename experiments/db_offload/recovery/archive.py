"""Lossless raw evidence compression with hashes; no old evidence touched."""
import argparse,gzip,hashlib,json
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();records=[]
 for path in sorted(a.root.rglob('*')):
  if not path.is_file() or path.suffix not in {'.json','.jsonl'} or path.name in {'summary.json','compression.json'} or path.stat().st_size<100000:continue
  raw=path.read_bytes();out=Path(str(path)+'.gz');out.write_bytes(gzip.compress(raw,mtime=0));path.unlink();records.append({'file':str(out.relative_to(a.root)),'uncompressed_sha256':hashlib.sha256(raw).hexdigest(),'compressed_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'raw_bytes':len(raw)})
 if records:
  target=a.root/'compression.json';old=json.loads(target.read_text()) if target.exists() else [];target.write_text(json.dumps(old+records,indent=2))
if __name__=='__main__':main()
