# Neopact plugin

Connect Codex to your Neopact buyer or seller workspace. Find products, prepare purchase requests, manage listings, negotiate within your business rules, and review orders. Both businesses' humans approve the exact offer in the Neopact dashboard.

The plugin runs locally over stdio. It includes the MCP adapter, a private setup wizard, and agent workflow instructions. You supply a running [Neopact backend](https://github.com/iivko/crossroads-backend) and your own restricted workspace credential.

## Install in Codex

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and make sure `uv` and `codex` are available in your terminal. Then run:

```sh
codex plugin marketplace add Sashe-Bashe/neopact-plugin
codex plugin add neopact@neopact
```

Restart Codex or start a new chat so the installed skills become available, then ask:

> Run Neopact setup.

The setup skill guides you to create a restricted agent credential in your dashboard's **Connections** view and run the local wizard in your own interactive terminal. The wizard asks for your API root (ending in `/api/v1`), workspace ID, and token with **hidden token input**. It verifies the connection before saving private configuration outside the plugin. Keep tokens out of chat and command arguments. Restart or reconnect the plugin after setup.

## Manual connection setup

If you prefer to run the wizard directly, clone this repository and run it from the repository root:

```sh
git clone https://github.com/Sashe-Bashe/neopact-plugin.git
cd neopact-plugin
uv run --project plugins/neopact/server --locked --no-dev python plugins/neopact/scripts/configure.py
```

This configures the connection; install the plugin with the Codex commands above if you have not already done so. `uv` installs the locked dependencies and can provision Python 3.12 or newer. See the [plugin guide](plugins/neopact/README.md) for scopes, private configuration, other local MCP hosts, and troubleshooting.

## Try it

- “Show my Neopact inbox and the next steps for each negotiation.”
- “Find polypropylene stackable chairs deliverable to Sofia.”
- “Negotiate a lower deposit in this room within my existing budget and delivery requirements.”
- “Create a draft seller listing from these product details.”
- “Show my confirmed Neopact orders.”

Start with read scopes: `catalogue:read`, `images:read`, `negotiations:read`, and `orders:read`. Add `negotiations:act` to negotiate, buyer `requests:write` to create or launch requests, or seller `products:write` to manage listings. Each connection represents one buyer or seller workspace; each person uses their own credential.

## Deployment and limits

Your backend must be reachable **from the computer running the plugin**. A recipient's `localhost` is their own computer. The plugin does not start or host the backend, expose it to the internet, or share the author's connection. A local backend works; an existing reachable HTTPS API works too. Trusted-LAN HTTP requires explicit opt-in for a private IPv4 address in the wizard.

Direct **ChatGPT web is not supported** by this local stdio release. It would require a separately reachable authenticated MCP service. Installing or sharing this repository does not provide that service.

The current marketplace supports chairs and integer EUR cents. Image tools return metadata, not pixels. Agent agreement moves to human review; it does not approve, pay for, or fulfil an order. Current confirmed orders are demo records.

## Development

Run the configuration and stdio transport checks from the repository root:

```sh
uv run --project plugins/neopact/server --locked --no-dev python -m unittest discover -s tests -v
```

The 24 tests pass on Python 3.12 and 3.14. A GitHub Actions template for Ubuntu and macOS is included at [`ci/plugin-tests.yml`](ci/plugin-tests.yml). To enable it, move it to `.github/workflows/test.yml` using a GitHub credential with workflow permissions.

The marketplace manifest is at `.agents/plugins/marketplace.json`; its `neopact` entry points to `./plugins/neopact`. See [NOTICE](plugins/neopact/NOTICE.md) for upstream provenance and licensing information. This repository does not assert an upstream open-source license.
