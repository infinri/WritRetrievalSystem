"""Supported local-owner mutations; context/inspect form the read-only agent surface."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from writ_retrieval.retrieval.embeddings import OnnxEmbeddingModel
from .contracts import canonical
from .store import ReliableStore, Key
from .git_history import export_history
from .ingest import ingest_history
from .session import ReliableSession
from .budget import Budget

MODEL_HASHES={'model.onnx':'6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452',
              'tokenizer.json':'be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037'}


def load_json(path):
    if Path(path).stat().st_size>16_000_000: raise ValueError("JSON input exceeds 16 MB limit")
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value: raise ValueError('duplicate JSON key: '+key)
            value[key]=item
        return value
    return json.loads(Path(path).read_text(),object_pairs_hook=unique,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('nonfinite JSON')))


def encoder(path):
    hashes={name:hashlib.sha256((Path(path)/name).read_bytes()).hexdigest() for name in MODEL_HASHES}
    if hashes!=MODEL_HASHES: raise ValueError('model artifacts differ from pinned public ONNX/tokenizer')
    from .contracts import digest
    return OnnxEmbeddingModel(Path(path)),digest(hashes)


def main(argv=None,*,agent_only=False):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store',type=Path,required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    context=commands.add_parser('context');context.add_argument('text');context.add_argument('--project',required=True)
    context.add_argument('--model-dir',type=Path,required=True);context.add_argument('--cache-dir',type=Path,required=True)
    context.add_argument('--arm',choices=('lexical','vector','hybrid','connected'),default='connected')
    context.add_argument('--max-bytes',type=int,default=8000);context.add_argument('--max-chars',type=int,default=6000)
    context.add_argument('--estimated-tokens',type=int);context.add_argument('--require',action='append',default=[],help='qualified Key.token; failure if required record cannot fit')
    context.add_argument('--inspect',action='store_true',help='owner diagnostics wrapper; only payload is model-facing')
    inspect=commands.add_parser('inspect');inspect.add_argument('ref',help='JSON project/label/id reference');inspect.add_argument('--project',required=True);inspect.add_argument('--generation');inspect.add_argument('--cache-dir',type=Path)
    if not agent_only:
        for name in ('capture','claim','evidence','conflict','retract','feedback','confirm','propose','revise','lifecycle','review-prepare','review-apply'):
            sub=commands.add_parser(name);sub.add_argument('input',type=Path)
        imp=commands.add_parser('history-import');imp.add_argument('input',type=Path);imp.add_argument('--project',default='writ-history');imp.add_argument('--verify-repo',type=Path);imp.add_argument('--create',action='store_true')
        git=commands.add_parser('git-ingest');git.add_argument('--repo',type=Path,required=True);git.add_argument('--end',required=True);git.add_argument('--limit',type=int,default=12);git.add_argument('--project',default='writ-history');git.add_argument('--create',action='store_true')
    args=parser.parse_args(argv)
    try:
        with ReliableStore(args.store,create=getattr(args,'create',False),initialize=not agent_only) as store:
            name=args.command
            if name=='context':
                model,identity=encoder(args.model_dir)
                result=ReliableSession(store,model,encoder_id=identity,cache_dir=args.cache_dir).context(args.text,project=args.project,arm=args.arm,
                    budget=Budget(args.max_bytes,args.max_chars,args.estimated_tokens),required=args.require)
                if result.get('error'):
                    print(canonical(result),file=sys.stderr);return 2
                print(canonical(result) if args.inspect else result['payload']);return 0
            if name=='inspect':
                ref=Key.parse(json.loads(args.ref));export=store.export();node=export['nodes'].get(ref)
                selected_revision=export['revision'];selected_generation=None
                if args.generation:
                    import re
                    from .contracts import digest
                    if not args.cache_dir or not re.fullmatch(r'sha256:[0-9a-f]{64}',args.generation): raise ValueError('generation requires a cache directory and exact digest')
                    directory=args.cache_dir/export['store_id']/args.generation[7:]
                    manifest=load_json(directory/'manifest.json');raw=(directory/'snapshot.json').read_bytes()
                    if manifest['generation']!=args.generation or hashlib.sha256(raw).hexdigest()!=manifest['files']['snapshot.json']: raise ValueError('snapshot artifact digest mismatch')
                    document=json.loads(raw)
                    if digest(document)!=manifest['source_digest']: raise ValueError('source snapshot digest mismatch')
                    node=next((n for r,n in document['nodes'] if Key.parse(r)==ref),None)
                    selected_revision=manifest['revision'];selected_generation=args.generation
                from writ_retrieval.retrieval.node_scope import is_visible
                if node is None or not is_visible(ref.label,ref.project,args.project): raise ValueError('record not found in visible project')
                # Owner/agent caller selects its local project; this is not an authenticated tenant API.
                from .contracts import binding_for
                result={'store_revision':selected_revision,'generation':selected_generation,'current_store_revision':export['revision'],'ref':ref.as_dict(),'record':node,'binding':binding_for(ref,node),
                        'note':'read-only local-owner data inspection, not approval'}
            elif name=='history-import': result=ingest_history(store,load_json(args.input),project=args.project,verify_repo=args.verify_repo)
            elif name=='git-ingest':
                history=export_history(args.repo,args.end,limit=args.limit)
                result=ingest_history(store,history,project=args.project,verify_repo=args.repo)
            elif name=='review-prepare':
                from .review import prepare_review
                result=prepare_review(store,load_json(args.input)['ref'])
            elif name=='review-apply':
                from .review import apply_review
                value=load_json(args.input);result=apply_review(store,value['artifact'],action=value['action'])
            elif name=='propose': result=store.propose(load_json(args.input))
            elif name=='revise': result=store.revise_proposal(**load_json(args.input))
            elif name=='lifecycle': result=store.lifecycle(**load_json(args.input))
            elif name=='capture': result=store.capture(load_json(args.input))
            elif name=='claim':
                value=load_json(args.input);result=store.add_claim(value['claim'],supersedes=value.get('supersedes'))
            elif name=='evidence': result=store.add_evidence(load_json(args.input))
            elif name=='conflict': result=store.declare_conflict(**load_json(args.input))
            elif name=='retract': result=store.retract_evidence(**load_json(args.input))
            elif name=='feedback': result=store.feedback_bound(**load_json(args.input))
            elif name=='confirm': result=store.confirm_evidence(load_json(args.input)['refs'])
            print(canonical(result));return 0
    except Exception as exc:
        print(canonical({'error':{'kind':type(exc).__name__,'message':str(exc)}}),file=sys.stderr);return 2


if __name__=='__main__': raise SystemExit(main())
