"""Behavioral checks using throwaway config directories and fake credentials."""

import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "neopact"
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import configure
import launch
import plugin_config as config


FAKE_TOKEN = "am_" + "fake_test_only_" * 4
OTHER_TOKEN = "am_" + "different_fake_" * 4


class PluginConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root / "neopact" / "plugin.json"
        self.identity = config.configuration_from_values("https://market.example/api/v1", "workspace-test", FAKE_TOKEN)

    def tearDown(self):
        self.temporary.cleanup()

    def environment(self, token=OTHER_TOKEN):
        return {
            "NEOPACT_MCP_API_URL": "https://another.example/api/v1",
            "NEOPACT_MCP_WORKSPACE": "workspace-other",
            "NEOPACT_MCP_TOKEN": token,
        }

    def test_round_trip_private_file(self):
        config.write_config(self.path, self.identity)
        loaded = config.load_configuration({}, self.path)
        self.assertEqual(loaded, self.identity)
        self.assertNotIn(FAKE_TOKEN, repr(loaded))
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)

    def test_complete_environment_wins_without_reading_file(self):
        config.write_config(self.path, self.identity)
        with patch.object(config, "read_config", side_effect=AssertionError("Should not read file")):
            actual = config.load_configuration(self.environment(), self.path)
        self.assertEqual(actual.workspace_id, "workspace-other")
        self.assertEqual(actual.token, OTHER_TOKEN)

    def test_partial_environment_never_mixes_with_saved_identity(self):
        config.write_config(self.path, self.identity)
        for name, value in self.environment().items():
            with self.subTest(name=name), self.assertRaisesRegex(config.PluginConfigurationError, "Partial"):
                config.load_configuration({name: value}, self.path)

    def test_lan_flag_alone_does_not_modify_saved_identity(self):
        config.write_config(self.path, self.identity)
        with self.assertRaisesRegex(config.PluginConfigurationError, "Partial"):
            config.load_configuration({config.LAN_ENV: "true"}, self.path)

    def test_empty_environment_field_is_invalid_not_fallback(self):
        config.write_config(self.path, self.identity)
        with self.assertRaisesRegex(config.PluginConfigurationError, "Invalid"):
            config.load_configuration(self.environment(token=""), self.path)

    def test_missing_configuration_has_actionable_error(self):
        with self.assertRaisesRegex(config.PluginConfigurationError, "scripts/configure.py"):
            config.load_configuration({}, self.path)

    def test_malformed_json_does_not_leak_file_content(self):
        config.write_config(self.path, self.identity)
        self.path.write_text('{"token": "' + FAKE_TOKEN)
        with self.assertRaises(config.PluginConfigurationError) as raised:
            config.read_config(self.path)
        self.assertNotIn(FAKE_TOKEN, str(raised.exception))

    def test_unknown_schema_wrong_types_and_extra_keys_are_rejected(self):
        config.write_config(self.path, self.identity)
        original = json.loads(self.path.read_text())
        for change in ({"schema_version": 2}, {"schema_version": True}, {"token": 42}, {"allow_lan_http": "false"}, {"extra": FAKE_TOKEN}):
            with self.subTest(change=next(iter(change))):
                self.path.write_text(json.dumps(original | change))
                with self.assertRaises(config.PluginConfigurationError) as raised:
                    config.read_config(self.path)
                self.assertNotIn(FAKE_TOKEN, str(raised.exception))

    def test_oversized_file_is_rejected(self):
        config.write_config(self.path, self.identity)
        self.path.write_text(" " * (config.MAX_CONFIG_BYTES + 1))
        with self.assertRaisesRegex(config.PluginConfigurationError, "too large"):
            config.read_config(self.path)

    @unittest.skipUnless(os.name == "posix", "POSIX file modes")
    def test_unsafe_permissions_rejected_for_read_and_write(self):
        config.write_config(self.path, self.identity)
        for target, unsafe, secure in ((self.path, 0o644, 0o600), (self.path.parent, 0o755, 0o700)):
            with self.subTest(target=target.name):
                target.chmod(unsafe)
                with self.assertRaisesRegex(config.PluginConfigurationError, "mode"):
                    config.read_config(self.path)
                with self.assertRaisesRegex(config.PluginConfigurationError, "mode"):
                    config.write_config(self.path, self.identity, overwrite=True)
                target.chmod(secure)

    @unittest.skipUnless(os.name == "posix", "POSIX ownership")
    def test_wrong_owner_is_rejected(self):
        config.write_config(self.path, self.identity)
        with patch.object(config.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaisesRegex(config.PluginConfigurationError, "owner"):
                config.read_config(self.path)

    def test_symlink_file_and_directory_are_rejected(self):
        config.write_config(self.path, self.identity)
        target = self.path.with_name("real.json")
        self.path.rename(target)
        try:
            self.path.symlink_to(target)
        except OSError:
            self.skipTest("Symlinks unavailable")
        for action in (lambda: config.read_config(self.path), lambda: config.write_config(self.path, self.identity, overwrite=True)):
            with self.assertRaisesRegex(config.PluginConfigurationError, "symbolic"):
                action()
        self.path.unlink()
        target.rename(self.path)
        real_directory = self.root / "real-neopact"
        self.path.parent.rename(real_directory)
        self.path.parent.symlink_to(real_directory, target_is_directory=True)
        with self.assertRaisesRegex(config.PluginConfigurationError, "symbolic"):
            config.read_config(self.path)

    def test_existing_config_requires_explicit_overwrite(self):
        config.write_config(self.path, self.identity)
        other = config.load_configuration(self.environment(), self.path)
        with self.assertRaisesRegex(config.PluginConfigurationError, "already configured"):
            config.write_config(self.path, other)
        self.assertEqual(config.read_config(self.path), self.identity)
        config.write_config(self.path, other, overwrite=True)
        self.assertEqual(config.read_config(self.path), other)
        self.assertEqual([item.name for item in self.path.parent.iterdir()], ["plugin.json"])

    def test_lan_http_requires_explicit_opt_in(self):
        env = self.environment() | {"NEOPACT_MCP_API_URL": "http://192.168.1.22:8000/api/v1"}
        with self.assertRaises(config.PluginConfigurationError):
            config.load_configuration(env, self.path)
        self.assertTrue(config.load_configuration(env | {config.LAN_ENV: "true"}, self.path).allow_lan_http)
        with self.assertRaisesRegex(config.PluginConfigurationError, "true or false"):
            config.load_configuration(env | {config.LAN_ENV: "yes"}, self.path)

    @unittest.skipUnless(os.name == "posix", "XDG paths")
    def test_xdg_config_path_and_relative_rejection(self):
        self.assertEqual(config.config_path({"XDG_CONFIG_HOME": str(self.root)}), self.path)
        with self.assertRaisesRegex(config.PluginConfigurationError, "absolute"):
            config.config_path({"XDG_CONFIG_HOME": "relative"})

    def test_validation_errors_do_not_repeat_bad_values(self):
        for args in (("https://example.invalid/" + FAKE_TOKEN, "workspace", FAKE_TOKEN), ("https://[" + FAKE_TOKEN, "workspace", FAKE_TOKEN), ("https://market.example/api/v1", "bad " + FAKE_TOKEN, FAKE_TOKEN)):
            with self.subTest(case=args[0]), self.assertRaises(config.PluginConfigurationError) as raised:
                config.configuration_from_values(*args)
            self.assertNotIn(FAKE_TOKEN, str(raised.exception))

    def test_setup_identity_failure_is_secret_safe_and_closes_client(self):
        with patch("mcp_server.client.Marketplace") as client:
            client.return_value.validate_identity = AsyncMock(side_effect=RuntimeError(FAKE_TOKEN))
            client.return_value.close = AsyncMock()
            with self.assertRaises(config.PluginConfigurationError) as raised:
                asyncio.run(configure.verify_identity(self.identity))
            self.assertNotIn(FAKE_TOKEN, str(raised.exception))
            client.return_value.close.assert_awaited_once()

    def test_launcher_failure_is_secret_safe_and_stdout_stays_empty(self):
        out, error = io.StringIO(), io.StringIO()
        with patch.object(launch, "load_configuration", side_effect=RuntimeError(FAKE_TOKEN)), redirect_stdout(out), redirect_stderr(error):
            self.assertEqual(launch.main(), 1)
        self.assertEqual(out.getvalue(), "")
        self.assertNotIn(FAKE_TOKEN, error.getvalue())
        self.assertIn("could not start", error.getvalue())

    def test_setup_rejects_credential_arguments_without_echoing_them(self):
        error = io.StringIO()
        with patch.object(sys, "argv", ["configure.py", "--token", FAKE_TOKEN]), redirect_stderr(error):
            with self.assertRaises(SystemExit) as raised:
                configure.main()
        self.assertEqual(raised.exception.code, 2)
        self.assertNotIn(FAKE_TOKEN, error.getvalue())

    def test_setup_refuses_noninteractive_secret_input(self):
        error = io.StringIO()
        with patch.object(sys, "argv", ["configure.py"]), patch.object(sys.stdin, "isatty", return_value=False), patch.object(configure.getpass, "getpass") as prompt, redirect_stderr(error):
            self.assertEqual(configure.main(), 2)
            prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
