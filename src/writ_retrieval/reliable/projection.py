"""Disposable, immutable native Relate indexes derived from one canonical snapshot.

A permitted-set partition is an application visibility materialization, not database
access control. This module never writes canonical records, observations or approvals.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import relate
from .contracts import canonical, digest


def keywords(text):
    return ' '.join(re.findall(r'[^\W_]+', text[:2000].lower(), re.UNICODE))


def file_digests(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and p.name not in {'.cypherlite.lock','.cypherlite.writer'}}


class RelateProjection:
    def __init__(self, root, *, generation, project, rows):
        self.expected = {r['uid']:r for r in rows}
        if len(self.expected)!=len(rows): raise ValueError('duplicate projection identity')
        self.identity=digest({'contract_version':'writ-native-projection/1','generation':generation,
                              'project':project,'rows':rows,'engine':'relate-db==1.0.1',
                              'search':'exact cosine; native fulltext; application RRF'})
        root=Path(root)/'projections';root.mkdir(parents=True,exist_ok=True)
        self.path=root/self.identity[7:];self.db=None
        if not self.path.exists():
            temporary=Path(tempfile.mkdtemp(prefix='.building-',dir=root));db=None
            try:
                db=relate.connect(str(temporary/'index.relate'))
                for offset in range(0,len(rows),128):
                    db.execute('UNWIND $rows AS r CREATE (n:Candidate) SET n += r',{'rows':rows[offset:offset+128]})
                # Empty partitions are valid; no global search followed by scope filtering.
                db.execute('CREATE VECTOR INDEX cv FOR (n:Candidate) ON n.embedding WITH [n.partition]')
                db.execute('CREATE FULLTEXT INDEX cf FOR (n:Candidate) ON EACH [n.text]')
                db.execute('CREATE (:Projection {identity:$id})',{'id':self.identity})
                db.close();db=None
                manifest={'contract_version':'writ-native-projection/1','identity':self.identity,
                          'generation':generation,'project':project,'row_count':len(rows),
                          'rows_digest':digest(rows),'database_files':file_digests(temporary/'index.relate')}
                (temporary/'manifest.json').write_text(canonical(manifest))
                for file in temporary.rglob('*'):
                    if file.is_file():
                        with file.open('rb') as stream: os.fsync(stream.fileno())
                os.rename(temporary,self.path)
                fd=os.open(root,os.O_RDONLY)
                try:os.fsync(fd)
                finally:os.close(fd)
            finally:
                if db is not None:db.close()
                if temporary.exists():shutil.rmtree(temporary)
        self.manifest=json.loads((self.path/'manifest.json').read_text())
        if self.manifest.get('identity')!=self.identity or self.manifest.get('rows_digest')!=digest(rows) or self.manifest.get('row_count')!=len(rows):
            raise ValueError('projection manifest does not bind this canonical generation')
        self.validate_file()
        self.db=relate.connect(str(self.path/'index.relate'),read_only=True)
        try:self.validate_rows()
        except Exception:self.close();raise

    def validate_file(self):
        if file_digests(self.path/'index.relate')!=self.manifest['database_files']:
            raise ValueError('projection database digest mismatch')
        if json.loads((self.path/'manifest.json').read_text())!=self.manifest:
            raise ValueError('projection manifest changed')

    def validate_rows(self):
        found=[dict(r) for r in self.db.execute('MATCH (n:Candidate) RETURN n.uid AS uid,n.text AS text,n.embedding AS embedding,n.payload AS payload,n.partition AS partition ORDER BY uid')]
        if digest(found)!=digest(sorted(self.expected.values(),key=lambda r:r['uid'])):
            raise ValueError('projection search text/vector/citation bindings differ from canonical export')
        marker=[dict(r) for r in self.db.execute('MATCH (n:Projection) RETURN n.identity AS identity')]
        if marker!=[{'identity':self.identity}]:raise ValueError('projection publication marker unavailable')

    def lists(self,text,vector,*,k,gate,mode):
        self.validate_file()  # Detect offline corruption even while an old read-only handle remains open.
        if not self.expected:return [],[]
        params={'q':keywords(text),'vector':list(map(float,vector)) if vector is not None else [],'scan':len(self.expected),'k':k,'gate':gate}
        lex=[];vec=[]
        if mode!='vector' and params['q']:
            lex=[dict(r) for r in self.db.execute("CALL db.index.fulltext.queryNodes('cf',$q) YIELD node,score RETURN node.uid AS uid,score ORDER BY score DESC,uid ASC LIMIT $k",params)]
        if mode!='lexical':
            # Relate reports (cosine+1)/2; compare raw cosine with the same gate as the exact oracle.
            vec=[dict(r) for r in self.db.execute("CALL db.index.vector.queryNodes('cv',$scan,$vector) YIELD node,score WITH node,2.0*score-1.0 AS cosine WHERE cosine >= $gate RETURN node.uid AS uid,cosine AS score ORDER BY score DESC,uid ASC LIMIT $k",params)]
        if any(r['uid'] not in self.expected for r in lex+vec):raise ValueError('projection returned an unbound candidate')
        return lex,vec

    def close(self):
        if self.db is not None:self.db.close();self.db=None


def quarantine_projection(store,cache_dir,identity):
    """Owner-only derived-cache recovery; retain damaged bytes and canonical data.

    Caller holds ReliableStore's local-owner lock. New contexts rebuild from the
    canonical export; this never declares a damaged generation current or verified.
    """
    import uuid
    if not isinstance(identity,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',identity):raise ValueError('exact projection digest required')
    export=store.export();root=Path(cache_dir)/export['store_id'];source=root/'projections'/identity[7:]
    if source.is_symlink() or not source.is_dir():raise ValueError('derived projection not found')
    manifest=source/'manifest.json'
    # Do not require a valid manifest to recover corruption, but bind the actual bytes.
    receipt={'contract_version':'writ-projection-quarantine/1','projection':identity,
             'source_revision':export['revision'],'recorded_at':store.clock(),
             'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else None,
             'purpose':'derived cache recovery only; canonical claims/evidence unchanged'}
    destination=root/'quarantine'/(identity[7:]+'-'+uuid.uuid4().hex);destination.parent.mkdir(exist_ok=True)
    os.rename(source,destination)
    (destination/'recovery-receipt.json').write_text(canonical(receipt))
    for path in (source.parent,destination.parent):
        fd=os.open(path,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    return {**receipt,'quarantined_path':str(destination),'next_step':'restart the context process and retrieve; indexes rebuild before publication'}
