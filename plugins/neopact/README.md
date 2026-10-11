# Neopact plugin guide

Use a desktop assistant with your own Neopact buyer or seller workspace. Search products, create purchase requests, maintain seller listings, negotiate supported terms, and read orders. Humans approve exact offers in the dashboard.

## Install and connect

You need Codex, [uv](https://docs.astral.sh/uv/getting-started/installation/) on the host's PATH, a reachable [Neopact backend](https://github.com/iivko/crossroads-backend), your workspace ID, and your own restricted agent credential from dashboard **Connections**.

Install from the repository's marketplace:

```sh
codex plugin marketplace add Sashe-Bashe/neopact-plugin
codex plugin add neopact@neopact
```

Restart Codex or start a new chat, then ask **“Run Neopact setup.”** The skill helps you run the packaged wizard in your own interactive terminal. The token prompt hides input; never paste a token into chat or pass it as a command argument. After setup, restart or reconnect the plugin and ask it to show your workspace role and negotiation inbox.

For direct manual setup, run these commands from a terminal:

```sh
git clone https://github.com/Sashe-Bashe/neopact-plugin.git
cd neopact-plugin
uv run --project plugins/neopact/server --locked --no-dev python plugins/neopact/scripts/configure.py
```

If the repository is already cloned, enter its root and run only the final command. When working directly inside this `plugins/neopact` directory, the equivalent command is:

```sh
uv run --project server --locked --no-dev python scripts/configure.py
```

The wizard asks for an API root ending in `/api/v1`, workspace ID, and restricted agent token. It verifies identity before saving private configuration outside the package. `uv` installs the locked runtime dependencies and can provision Python 3.12 or newer.

The marketplace belongs to the **repository root**, not this plugin directory. It is named `neopact` and points to `./plugins/neopact`; there is no nested marketplace to register here.

## Credentials and scopes

Begin with `catalogue:read`, `images:read`, `negotiations:read`, and `orders:read`. Add only capabilities needed for your tasks:

| Task | Additional scope |
| --- | --- |
| Negotiate or send room messages | `negotiations:act` |
| Create and launch buyer requests | Buyer `requests:write` |
| Create or update seller listings | Seller `products:write` |

All 13 tools are discoverable, but the backend enforces the configured credential's role, workspace, and scopes. Buyer and seller connections need separate credentials. Do not use a browser session or administrator credential, or share one person's credential with other users.

On macOS/Linux, private configuration is saved to `$XDG_CONFIG_HOME/neopact/plugin.json` or `~/.config/neopact/plugin.json`. Windows uses `%APPDATA%/neopact/plugin.json`. On POSIX, the directory and file use owner-only permissions (0700/0600); on Windows, keep the profile directory private through filesystem access controls. Never share this file or commit it to source control.

## Backend access

This package contains the adapter and instructions, not the backend or accounts. The backend must be reachable from each recipient's computer. Their `localhost` refers to their computer, not the marketplace owner's. Keep a local-only backend local unless its owner separately decides to make it reachable.

Remote connections require HTTPS by default. For an existing trusted-LAN demo, the wizard permits explicit HTTP opt-in only for literal private IPv4 addresses. Use demo credentials in that mode. The plugin does not create a tunnel or deploy a service.

**ChatGPT web cannot directly use this local stdio server.** Web support needs a separately reachable authenticated MCP service. Saving the plugin to an account or sharing this repository does not host the backend or supply remote OAuth.

## Example prompts

- “Show my negotiation inbox and available next steps.”
- “Find wood chairs deliverable to Sofia and compare asking prices and delivery charges.”
- “Continue this negotiation using my latest private guidance.”
- “Negotiate a lower deposit while preserving my existing price and delivery constraints.”
- “Update the stock on my listing to 80.”
- “Show my confirmed orders.”

## Other local MCP hosts

Register a stdio server using the absolute path to this plugin directory in your clone:

```json
{
  "mcpServers": {
    "neopact": {
      "command": "uv",
      "args": [
        "run", "--project", "/absolute/path/neopact-plugin/plugins/neopact/server",
        "--locked", "--no-dev", "python",
        "/absolute/path/neopact-plugin/plugins/neopact/scripts/launch.py"
      ]
    }
  }
}
```

If a desktop host cannot find `uv`, fix its PATH or use the absolute path to your installed `uv` executable. Portable plugin hosts use `plugin.json` and `mcp.json`; Codex compatibility manifests are included. The adapter needs no local database or backend checkout.

Advanced hosts can provide the complete identity through their protected environment facility: `NEOPACT_MCP_API_URL`, `NEOPACT_MCP_WORKSPACE`, and `NEOPACT_MCP_TOKEN`. Add `NEOPACT_MCP_ALLOW_LAN_HTTP=true` only for explicit trusted-LAN mode. A complete environment identity overrides the saved configuration; a partial identity is rejected. Keep values out of shared manifests, screenshots, shell arguments, and chat. Use separate protected environments for simultaneous buyer and seller processes; the default wizard config represents one workspace.

## Tools and limits

Seven reads: `get_instructions`, `search_catalogue`, `get_product_images`, `get_inbox`, `get_negotiation_context`, `get_activity`, and `get_orders`.

Six writes: `create_request`, `launch_request`, `create_product`, `update_product`, `claim_turn`, and `submit_action`.

The current catalogue supports chairs. Money is integer EUR cents. Image reads return metadata, not pixels or visual inspection. Agents cannot change business rules, waive requirements, issue credentials, switch workspaces, or approve as a human. Negotiation acceptance moves to review by both humans; confirmed demo orders are not payments or proof of fulfilment. See the [workflow guide](skills/neopact-marketplace/SKILL.md) and [tool reference](skills/neopact-marketplace/references/tools.md).

## Updating, disconnecting, and testing

Run the wizard again to replace the saved connection; it asks before overwriting. Reconnect the host after a credential change and revoke the old credential in dashboard **Connections**. Remove the plugin with `codex plugin remove neopact@neopact` or the host's uninstall control. Uninstalling does not revoke a credential; delete private configuration separately when no longer needed.

From the repository root, run:

```sh
uv run --project plugins/neopact/server --locked --no-dev python -m unittest discover -s tests -v
```

See [NOTICE](NOTICE.md) for source provenance. The adapter comes from the [Neopact backend](https://github.com/iivko/crossroads-backend); no upstream open-source license was present in the inspected source, and this package does not assert or grant one. Third-party dependencies retain their own licenses.
