---
description: Sync agent definitions from .opencode/agent(s)/ files into opencode.json
---

Run the agent sync script to import all agent definitions from `.opencode/agent/` and `.opencode/agents/` into `opencode.json`.

Execute this command:

```
python scripts/sync-agents.py
```

If the script prompts for confirmation, respond with "y" to apply changes. Report the summary of agents added, updated, and skipped.
