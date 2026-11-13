"""Thin local agent interface: knowledge reads only, no approval or mutation verbs."""
from .cli import main
if __name__=='__main__': raise SystemExit(main(agent_only=True))
