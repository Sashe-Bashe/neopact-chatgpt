#!/usr/bin/env python3
"""Start the original Neopact stdio server with one complete identity."""

import logging
import sys

from plugin_config import PluginConfigurationError, load_configuration


def main() -> int:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    try:
        config = load_configuration()
        from mcp_server.client import Marketplace
        from mcp_server.server import create_server

        create_server(Marketplace(config)).run(transport="stdio", show_banner=False)
        return 0
    except PluginConfigurationError as error:
        print(f"Neopact: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception:
        # Exceptions from dependencies or a backend must never echo credentials.
        print("Neopact could not start. Check the connection, run scripts/configure.py in a terminal, and restart the plugin.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
