---
name: setup
description: Set up the Neopact desktop plugin, connect a buyer or seller workspace, or repair a missing local connection.
---

# Set up Neopact

This release uses a local stdio MCP process. Direct ChatGPT web connections are not implemented. Never expose it through an unauthenticated HTTP adapter or reuse one credential for other users.

1. Locate this installed plugin directory and read its `README.md`. Check that `uv` is available. Resolve actual plugin paths; do not assume the author's checkout exists.
2. Ask for the Neopact API address and the buyer or seller workspace only if they are unknown. Each recipient needs a running backend reachable from their own computer. Their localhost is their own machine, not the author's.
3. Direct the person to their Neopact dashboard's Connections view to create a restricted workspace agent credential. Begin with read scopes; add only the write scopes their task needs. Do not issue credentials on their behalf or use browser/admin credentials.
4. Have them run the packaged `scripts/configure.py` using the command in `README.md` in their own interactive terminal. It prompts for the token with hidden input, verifies identity, and stores private local configuration outside the package. Do not ask them to paste a token into chat or pass one as a command argument. Do not read the resulting credential file.
5. Install through the packaged local marketplace or supported desktop plugin flow, then reconnect/restart the host. Environment configuration is an optional advanced path described in the README.
6. Verify with `get_instructions`, `get_inbox`, and a bounded `search_catalogue` call. Confirm the returned role/workspace with the user. Never perform mutations just to test access. If tools are unavailable, finish local setup and request host reconnection; do not claim success without a harmless live call.

A read-only credential may discover write tools but cannot use them. If writing is denied, explain the missing scope and let the owner issue a correctly scoped credential in Connections. Never bypass role, workspace, human approval, or network restrictions.
