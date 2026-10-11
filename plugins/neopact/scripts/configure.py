#!/usr/bin/env python3
"""Interactive onboarding; never pass a token through arguments or stdout."""

import argparse
import asyncio
import getpass
import sys
import warnings

from plugin_config import PluginConfigurationError, config_path, configuration_from_values, write_config


class SecretSafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Neopact setup accepts no credential arguments. Run it without arguments in an interactive terminal.\n")


async def verify_identity(config) -> None:
    from mcp_server.client import Marketplace

    api = Marketplace(config)
    try:
        await api.validate_identity()
    except Exception:
        # Backend messages are untrusted and could repeat the submitted token.
        raise PluginConfigurationError(
            "Connection verification failed. Check the API URL, workspace ID, restricted agent token, and backend availability. No configuration was saved."
        ) from None
    finally:
        await api.close()


def main() -> int:
    parser = SecretSafeArgumentParser(description="Configure a private Neopact workspace connection. Credentials are entered interactively.")
    parser.parse_args()
    if not sys.stdin.isatty():
        print("Neopact setup needs an interactive terminal so the token can be entered without echo.", file=sys.stderr)
        return 2
    try:
        path = config_path()
        print("Neopact setup connects one buyer or seller workspace using its restricted agent token.")
        print(f"Private configuration: {path}")
        overwrite = path.exists() or path.is_symlink()
        if overwrite and input("Replace the existing configuration? Type yes to continue: ").strip().lower() != "yes":
            print("Setup cancelled; existing configuration retained.")
            return 0
        api_url = input("Marketplace API URL (include /api/v1): ").strip()
        workspace_id = input("Workspace ID: ").strip()
        allow_lan = False
        if api_url.lower().startswith("http://"):
            allow_lan = input("Allow unencrypted HTTP to a trusted private IPv4 LAN address? Type yes to opt in (otherwise loopback only): ").strip().lower() == "yes"
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            token = getpass.getpass("Restricted workspace agent token (hidden): ")
        config = configuration_from_values(api_url, workspace_id, token, allow_lan)
        print("Verifying the restricted workspace identity…")
        asyncio.run(verify_identity(config))
        write_config(path, config, overwrite=overwrite)
        print("Connection verified and private configuration saved. Restart or reconnect the Neopact plugin.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled.", file=sys.stderr)
        return 130
    except PluginConfigurationError as error:
        print(f"Neopact: {error}", file=sys.stderr)
        return 2
    except Exception:
        print("Neopact setup failed; credentials were not displayed. Check terminal access and the private configuration directory, then retry.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
