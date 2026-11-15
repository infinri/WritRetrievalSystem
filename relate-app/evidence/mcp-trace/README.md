# Real host invocation of the read-only MCP server

One Claude Code session (CLI 2.1.325, requested and resolved model `claude-sonnet-5-5`,
effort low) through the owner's existing authorized login. This demonstrates a real host
calling the Rust interface. **It is not an agent experiment** and shows nothing about
task success.

- `mcp-config.json`: the server command. The binary runs in the dev container, and the
  store is `relate-app/demo-store` (read-only).
- `system-prompt.txt`, `task.txt`: the exact prompt.
- `trace.jsonl`: the full stream-json event log. Host-specific init fields (session id,
  memory/socket paths, API key source) and local paths are redacted; nothing else is
  changed.
- `summary.json`: tools available, the tool call, the final answer, turns and reported
  list cost.

Flags: `-p --setting-sources '' --strict-mcp-config --mcp-config … --tools ''
--allowedTools "mcp__writ__writ_context mcp__writ__writ_inspect" --disable-slash-commands
--permission-mode dontAsk --no-session-persistence --system-prompt …`. No
permission-bypass flag was used. `--safe-mode` was not used because it disables MCP servers.

The session saw exactly two tools, had no CLAUDE.md, memory, hooks or skills, and ran
from an empty temporary directory. The host still injects organization instructions and
account context into the system prompt; these are not in the committed trace. Earlier
recordings against the pre-final binary were replaced by this final one.
