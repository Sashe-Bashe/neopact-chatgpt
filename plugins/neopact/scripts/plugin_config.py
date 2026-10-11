"""Private, per-user configuration for the portable Neopact plugin.

Credentials are never stored in the plugin directory. Errors from this module
are intentionally fixed messages: malformed input must not reveal secrets.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Mapping

SERVER_ROOT = Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(SERVER_ROOT))

from mcp_server.config import Configuration  # noqa: E402


class PluginConfigurationError(ValueError):
    """A configuration problem safe to display without exposing input."""


CORE_ENV = ("NEOPACT_MCP_API_URL", "NEOPACT_MCP_WORKSPACE", "NEOPACT_MCP_TOKEN")
LAN_ENV = "NEOPACT_MCP_ALLOW_LAN_HTTP"
MAX_CONFIG_BYTES = 16_384


def config_path(environment: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environment is None else environment
    if os.name == "nt":
        root = Path(env["APPDATA"]) if env.get("APPDATA") else Path.home() / "AppData" / "Roaming"
    else:
        root = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else Path.home() / ".config"
    if not root.is_absolute():
        raise PluginConfigurationError("The user configuration directory must be an absolute path.")
    return root / "neopact" / "plugin.json"


def _reject_symlinks(path: Path) -> None:
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or (os.name == "nt" and part.is_junction()):
            raise PluginConfigurationError("Neopact configuration paths must not contain symbolic links.")


def _check_private(info: os.stat_result, *, directory: bool) -> None:
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected_type(info.st_mode):
        raise PluginConfigurationError("Neopact configuration must use a regular file in a private directory.")
    if os.name == "posix":
        required_mode = 0o700 if directory else 0o600
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != required_mode:
            raise PluginConfigurationError(
                "Neopact configuration requires the current user as owner, directory mode 0700, and file mode 0600."
            )


def _private_parent(path: Path, *, create: bool = False) -> None:
    _reject_symlinks(path)
    if create:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _check_private(path.parent.lstat(), directory=True)


def configuration_from_values(
    api_url: str, workspace_id: str, token: str, allow_lan_http: bool = False
) -> Configuration:
    if not all(isinstance(value, str) for value in (api_url, workspace_id, token)):
        raise PluginConfigurationError("Neopact API URL, workspace ID, and restricted token must be text values.")
    if type(allow_lan_http) is not bool:
        raise PluginConfigurationError("Neopact LAN HTTP opt-in must be true or false.")
    try:
        return Configuration(api_url, workspace_id, token, allow_lan_http)
    except Exception:
        raise PluginConfigurationError(
            "Invalid Neopact configuration. Use an HTTPS /api/v1 URL, one workspace ID, and its restricted am_ agent token. "
            "Loopback HTTP is allowed; private IPv4 HTTP requires explicit LAN opt-in."
        ) from None


def read_config(path: Path) -> Configuration:
    try:
        _private_parent(path)
        _check_private(path.lstat(), directory=False)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            _check_private(os.fstat(stream.fileno()), directory=False)
            raw = stream.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise PluginConfigurationError("Neopact configuration is too large. Run scripts/configure.py again.")
        data = json.loads(raw)
        expected = {"schema_version", "api_url", "workspace_id", "token", "allow_lan_http"}
        if not isinstance(data, dict) or set(data) != expected or type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise PluginConfigurationError("Neopact configuration has an unsupported format. Run scripts/configure.py again.")
        return configuration_from_values(data["api_url"], data["workspace_id"], data["token"], data["allow_lan_http"])
    except PluginConfigurationError:
        raise
    except FileNotFoundError:
        raise PluginConfigurationError(
            "Neopact is not configured. In a terminal, run: uv run --project <plugin-directory>/server --locked --no-dev python <plugin-directory>/scripts/configure.py"
        ) from None
    except (OSError, UnicodeError, ValueError, TypeError):
        raise PluginConfigurationError("Cannot read Neopact configuration. Check the private file or run scripts/configure.py again.") from None


def load_configuration(environment: Mapping[str, str] | None = None, path: Path | None = None) -> Configuration:
    env = os.environ if environment is None else environment
    present = [name in env for name in CORE_ENV]
    if any(present) or LAN_ENV in env:
        if not all(present):
            raise PluginConfigurationError(
                "Partial Neopact environment configuration. Set NEOPACT_MCP_API_URL, NEOPACT_MCP_WORKSPACE, and NEOPACT_MCP_TOKEN together, or remove all Neopact configuration variables and run setup."
            )
        lan_value = env.get(LAN_ENV, "false").strip().lower()
        if lan_value not in {"true", "false"}:
            raise PluginConfigurationError("NEOPACT_MCP_ALLOW_LAN_HTTP must be true or false.")
        return configuration_from_values(*(env[name] for name in CORE_ENV), allow_lan_http=lan_value == "true")
    return read_config(config_path(env) if path is None else path)


def write_config(path: Path, config: Configuration, *, overwrite: bool = False) -> None:
    """Atomically save a validated configuration, refusing implicit replacement."""
    config = configuration_from_values(config.api_url, config.workspace_id, config.token, config.allow_lan_http)
    temporary: Path | None = None
    try:
        _private_parent(path, create=True)
        if path.exists():
            _check_private(path.lstat(), directory=False)
            if not overwrite:
                raise PluginConfigurationError("Neopact is already configured. Confirm replacement in scripts/configure.py.")
        data = {
            "schema_version": 1,
            "api_url": config.api_url,
            "workspace_id": config.workspace_id,
            "token": config.token,
            "allow_lan_http": config.allow_lan_http,
        }
        descriptor, name = tempfile.mkstemp(prefix=".plugin-", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            if os.name == "posix":
                os.fchmod(stream.fileno(), 0o600)
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _private_parent(path)
        if overwrite:
            if path.exists():
                _check_private(path.lstat(), directory=False)
            os.replace(temporary, path)
        else:
            # Linking a completed temporary file is atomic and refuses a raced-in destination.
            os.link(temporary, path)
        temporary.unlink(missing_ok=True)
        temporary = None
    except PluginConfigurationError:
        raise
    except OSError:
        raise PluginConfigurationError("Cannot securely save Neopact configuration. Check directory access and retry setup.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
