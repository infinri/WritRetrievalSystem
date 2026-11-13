"""Read-only local agent CLI; deny network before loading third-party runtimes."""
def main(argv=None):
    from .offline import deny_network
    deny_network()
    from .cli import main as cli
    return cli(argv,agent_only=True)

if __name__=='__main__': raise SystemExit(main())
