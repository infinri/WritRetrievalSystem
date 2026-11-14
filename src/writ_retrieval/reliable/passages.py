"""Read-only, exact-revision paragraph capture through supported Claim APIs.

Git identity is mechanically checked; repository statements remain unverified.
No claims about approvals, successful tools, rationale or outcomes are inferred.
"""
from __future__ import annotations
import hashlib
from pathlib import PurePosixPath
import re
from .git_history import git, utc, PUBLIC_REPOSITORY
from .contracts import Claim, canonical, digest, text_digest, instant
from .store import Key


def export_passages(repo,revision,paths):
    if not re.fullmatch(r'[0-9a-f]{40}',revision):raise ValueError('exact forty-hex Git revision required')
    if not 1<=len(paths)<=32 or len(set(paths))!=len(paths):raise ValueError('1..32 distinct source paths required')
    for path in paths:
        p=PurePosixPath(path)
        if p.is_absolute() or '..' in p.parts or str(p)!=path or not path.endswith('.md'):raise ValueError('normalized repository Markdown path required')
    if git(repo,'rev-parse','--verify',revision+'^{commit}').decode().strip()!=revision:raise ValueError('Git revision mismatch')
    license_text=git(repo,'show',revision+':LICENSE').decode()
    if 'MIT License' not in license_text:raise ValueError('expected public MIT Writ source')
    recorded_at=utc(git(repo,'show','-s','--format=%cI',revision).decode().strip());documents=[];total=0
    for path in paths:
        text=git(repo,'show',revision+':'+path).decode();total+=len(text.encode())
        if total>8_000_000:raise ValueError('source bytes exceed 8 MB limit')
        headings=list(re.finditer(r'(?m)^## (.+)$',text))
        for h,match in enumerate(headings):
            end=headings[h+1].start() if h+1<len(headings) else len(text)
            section=text[match.end():end]
            for part in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)',section):
                passage=part.group().strip();start=text.find(passage,match.end()+part.start());stop=start+len(passage)
                if len(passage)<70 or len(passage)>1600 or passage.startswith(('~~~','```','<','|')):continue
                uid=hashlib.sha256((path+'\0'+str(start)+'\0'+passage).encode()).hexdigest()[:24]
                documents.append({'id':uid,'path':path,'heading':match.group(1),'text':passage,'start':start,'end':stop,
                    'start_line':text[:start].count('\n')+1,'end_line':text[:stop].count('\n')+1,'revision':revision,
                    'committed_at':recorded_at,'source_digest':hashlib.sha256(text.encode()).hexdigest(),
                    'content_digest':text_digest(passage),'uri':f'{PUBLIC_REPOSITORY}/blob/{revision}/{path}#L{text[:start].count(chr(10))+1}'})
                if len(documents)>1000:raise ValueError('source passage count exceeds 1000')
    return {'contract_version':'writ-passage-import/1','repository':PUBLIC_REPOSITORY,'revision':revision,
            'recorded_at':recorded_at,'documents':documents,'paths':list(paths),
            'unknowns':'Repository assertions unverified; commit identity is not approval, successful verification or known outcome.'}


def ingest_passages(store,document,*,project,verify_repo=None):
    if document.get('contract_version')!='writ-passage-import/1' or document.get('repository')!=PUBLIC_REPOSITORY:raise ValueError('unsupported passage import contract')
    if set(document)!={'contract_version','repository','revision','recorded_at','documents','paths','unknowns'}:raise ValueError('unexpected passage import fields')
    instant(document['recorded_at'])
    if verify_repo is not None:
        actual=export_passages(verify_repo,document['revision'],document['paths'])
        if digest(actual)!=digest(document):raise ValueError('passages differ from exact Git objects')
    receipt=Key(project,'ReliableReceipt','passages:'+digest(document)[7:]);request_digest=digest(document)
    with store.transaction():
        old=store.get(receipt)
        if old:
            if old['request_digest']!=request_digest:raise ValueError('passage receipt mismatch')
            return {'replayed':True,'receipt':receipt.as_dict(),'passages':len(document['documents'])}
        for item in document['documents']:
            if set(item)!={'id','path','heading','text','start','end','start_line','end_line','revision','committed_at','source_digest','content_digest','uri'}:raise ValueError('unexpected passage fields; imports cannot award trust')
            if item['path'] not in document['paths'] or item['revision']!=document['revision'] or item['committed_at']!=document['recorded_at']:raise ValueError('passage revision/time/path mismatch')
            if type(item['start']) is not int or type(item['end']) is not int or item['start']<0 or item['end']-item['start']!=len(item['text']):raise ValueError('invalid passage character interval')
            expected=hashlib.sha256((item['path']+'\0'+str(item['start'])+'\0'+item['text']).encode()).hexdigest()[:24]
            if item['id']!=expected or item['content_digest']!=text_digest(item['text']):raise ValueError('passage identity/digest mismatch')
            if not re.fullmatch(r'[0-9a-f]{64}',item['source_digest']):raise ValueError('invalid source digest')
            value=Claim(**{'project':project,'claim_id':item['revision']+':'+item['id'],
                'topic':item['path']+'#'+item['heading'],'title':item['heading'],'text':item['text'],
                'content_digest':item['content_digest'],'kind':'repository_assertion','recorded_at':document['recorded_at'],
                'source':{'uri':item['uri'],'revision':item['revision'],'path':item['path'],
                    'committed_at':item['committed_at'],'start_line':item['start_line'],'end_line':item['end_line']}})
            value.check_at(store.clock());data=value.model_dump();key=Key(project,'Claim',value.claim_id)
            meaning=digest({'claim':data,'supersedes':None});existing=store.get(key)
            if existing:
                if existing.get('request_digest')!=meaning:raise ValueError('immutable passage claim changed')
            else:
                store._set(key,{**data,'source':canonical(data['source']),'revision':1,'status':'live',
                    'verification_status':'unverified','approval_status':'unknown','outcome_status':'unknown',
                    'request_digest':meaning,'provenance':'record'})
        store._set(receipt,{'project':project,'receipt_id':receipt.id,'request_digest':request_digest,
                           'source_revision':document['revision'],'git_objects_checked':verify_repo is not None,
                           'recorded_at':store.clock(),'provenance':'record'})
    return {'replayed':False,'receipt':receipt.as_dict(),'passages':len(document['documents']),
            'git_objects_checked':verify_repo is not None,'assertion_verification':'unverified'}
