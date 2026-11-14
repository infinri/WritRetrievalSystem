"""Opt-in offline read-only grounded context; mutations remain owner CLI operations."""
def main(argv=None):
    from .offline import deny_network
    deny_network()  # Before ONNX/Relate imports, same boundary as the legacy agent.
    import argparse,json,sys
    from pathlib import Path
    from .cli import encoder,load_json
    from .store import ReliableStore
    from .grounded import GroundedSession
    from .budget import Budget
    from .contracts import canonical
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--store',type=Path,required=True);p.add_argument('--cache-dir',type=Path,required=True)
    p.add_argument('--model-dir',type=Path,required=True);p.add_argument('--project',required=True)
    p.add_argument('--backend',choices=('flat','relate'),default='flat');p.add_argument('--arm',choices=('lexical','vector','hybrid','connected'),default='hybrid')
    p.add_argument('--request',type=Path);p.add_argument('--require',action='append',default=[])
    p.add_argument('--max-bytes',type=int,default=8000);p.add_argument('--max-chars',type=int,default=6000)
    p.add_argument('--inspect',action='store_true');p.add_argument('text');args=p.parse_args(argv)
    try:
        model,identity=encoder(args.model_dir)
        with ReliableStore(args.store,initialize=False) as store,GroundedSession(store,model,encoder_id=identity,cache_dir=args.cache_dir,backend=args.backend) as session:
            result=session.context(args.text,project=args.project,arm=args.arm,request=load_json(args.request) if args.request else None,
                required=args.require,budget=Budget(args.max_bytes,args.max_chars))
            if result.get('error'):print(canonical(result),file=sys.stderr);return 2
            print(canonical(result) if args.inspect else result['payload']);return 0
    except Exception as exc:
        print(canonical({'error':{'kind':type(exc).__name__,'message':str(exc)}}),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
