"""Pinned public optional runtimes, no privileged installation."""
import argparse,hashlib,json,tarfile,urllib.request
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);records={}
 urls={'neo4j-community-5.26.0-unix.tar.gz':'https://dist.neo4j.org/neo4j-community-5.26.0-unix.tar.gz','relate-ffi-1.0.1.tar.gz':'https://github.com/relatedb/relate/releases/download/v1.0.1/relate-ffi-x86_64-unknown-linux-gnu.tar.gz'}
 for name,url in urls.items():
  raw=urllib.request.urlopen(url,timeout=120).read();target=a.output/name;target.write_bytes(raw);records[name]={'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
  with tarfile.open(target) as archive:archive.extractall(a.output,filter='data')
 (a.output/'archives.json').write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':main()
