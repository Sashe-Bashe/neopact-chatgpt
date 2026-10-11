"""Exercise the shipped command over real stdio against a synthetic local API.

No real workspace, credential, config file, or remote service is used.
"""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "neopact"
FAKE_TOKEN = "am_" + "synthetic_stdio_test_only_" * 3
WORKSPACE = "workspace-stdio-fixture"
EXPECTED_TOOLS = {
    "get_instructions", "search_catalogue", "get_product_images", "get_inbox",
    "get_negotiation_context", "get_activity", "get_orders", "create_request",
    "launch_request", "create_product", "update_product", "claim_turn", "submit_action",
}


class LocalMarketplace(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), MarketplaceHandler)
        self.role = "buyer"
        self.credential_kind = "agent"
        self.workspace_id = WORKSPACE
        self.can_approve = False
        self.requests = []
        self.bad_authorization = False


class MarketplaceHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        server = self.server
        parsed = urlsplit(self.path)
        server.requests.append((parsed.path, parse_qs(parsed.query)))
        if self.headers.get("Authorization") != "Bearer " + FAKE_TOKEN or self.headers.get("X-Workspace-ID") != WORKSPACE:
            server.bad_authorization = True
            self.respond(401, "error", {"code": "unauthorized", "message": "Fixture credential mismatch"})
            return
        routes = {
            "/api/v1/auth/me": ("identity", {
                "credential": {"kind": server.credential_kind},
                "workspace": {"id": server.workspace_id, "role": server.role},
                "can_approve": server.can_approve,
            }),
            "/api/v1/agent/instructions": ("instructions", {"role": server.role, "workspace_id": WORKSPACE, "fixture": True}),
            "/api/v1/agent/inbox": ("inbox", {"rooms": [], "guidance": [], "fixture": True}),
            "/api/v1/products": ("catalogue", {"items": [{"id": "product-fixture", "material": "wood"}], "fixture": True}),
        }
        if parsed.path not in routes:
            self.respond(404, "error", {"code": "not_found", "message": "Unknown fixture route"})
            return
        label, body = routes[parsed.path]
        self.respond(200, label, body)

    def respond(self, status, label, resource):
        body = json.dumps({"status_code": status, label: resource}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class PackagedStdioTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name).resolve()
        self.log = self.directory / "server-stderr.log"
        self.api = LocalMarketplace()
        self.thread = threading.Thread(target=self.api.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        manifest = json.loads((PLUGIN_ROOT / "mcp.json").read_text())
        server = manifest["mcpServers"]["neopact"]
        substitute = lambda value: value.replace("${PLUGIN_ROOT}", str(PLUGIN_ROOT))
        environment = {name: os.environ[name] for name in ("PATH", "HOME", "USER", "SYSTEMROOT", "APPDATA") if name in os.environ}
        environment.update({
            "NEOPACT_MCP_API_URL": f"http://127.0.0.1:{self.api.server_port}/api/v1",
            "NEOPACT_MCP_WORKSPACE": WORKSPACE,
            "NEOPACT_MCP_TOKEN": FAKE_TOKEN,
            "NEOPACT_MCP_ALLOW_LAN_HTTP": "false",
            "XDG_CONFIG_HOME": str(self.directory / "unused-config"),
            "NO_COLOR": "1",
        })
        self.transport = StdioTransport(
            command=substitute(server["command"]),
            args=[substitute(argument) for argument in server["args"]],
            cwd=substitute(server["cwd"]),
            env=environment,
            keep_alive=False,
            log_file=self.log,
        )
        self.client = Client(self.transport, timeout=5, init_timeout=10)

    async def asyncTearDown(self):
        await asyncio.to_thread(self.api.shutdown)
        self.api.server_close()
        self.thread.join(timeout=2)
        try:
            if self.log.exists():
                self.assertNotIn(FAKE_TOKEN, self.log.read_text())
            self.assertFalse(self.api.bad_authorization, "Launcher sent an unexpected identity to the fixture")
        finally:
            self.temporary.cleanup()

    async def exercise_reads(self, role):
        self.api.role = role
        async with asyncio.timeout(20):
            async with self.client:
                tools = await self.client.list_tools()
                self.assertEqual({tool.name for tool in tools}, EXPECTED_TOOLS)
                self.assertEqual(len(tools), 13)
                instructions = await self.client.call_tool("get_instructions")
                self.assertFalse(instructions.is_error)
                self.assertEqual(instructions.data["role"], role)
                self.assertEqual(instructions.data["workspace_id"], WORKSPACE)
                inbox = await self.client.call_tool("get_inbox")
                self.assertFalse(inbox.is_error)
                self.assertEqual(inbox.data["rooms"], [])
                catalogue = await self.client.call_tool("search_catalogue", {
                    "query": "fixture furniture",
                    "own_products": role == "seller",
                    "material": "wood",
                    "limit": 5,
                    "offset": 0,
                })
                self.assertFalse(catalogue.is_error)
                self.assertEqual(catalogue.data["items"][0]["id"], "product-fixture")
        paths = [path for path, _ in self.api.requests]
        self.assertEqual(paths, ["/api/v1/auth/me", "/api/v1/agent/instructions", "/api/v1/agent/inbox", "/api/v1/products"])
        query = self.api.requests[-1][1]
        self.assertEqual(query["q"], ["fixture furniture"])
        self.assertEqual(query["own"], ["true" if role == "seller" else "false"])
        self.assertEqual(query["material"], ["wood"])
        self.assertEqual(query["limit"], ["5"])

    async def assert_identity_rejected(self):
        with self.assertRaises(Exception) as raised:
            async with asyncio.timeout(15):
                async with self.client:
                    self.fail("An unauthorized identity initialized the MCP session")
        self.assertNotIsInstance(raised.exception, (TimeoutError, AssertionError), "Identity rejection must be an explicit startup failure, not timeout")
        self.assertNotIn(FAKE_TOKEN, str(raised.exception))
        self.assertEqual([path for path, _ in self.api.requests], ["/api/v1/auth/me"])

    async def test_buyer_lists_13_tools_and_reads(self):
        await self.exercise_reads("buyer")

    async def test_seller_lists_13_tools_and_reads(self):
        await self.exercise_reads("seller")

    async def test_workspace_mismatch_fails_startup(self):
        self.api.workspace_id = "different-workspace"
        await self.assert_identity_rejected()

    async def test_owner_credential_fails_startup(self):
        self.api.credential_kind = "owner"
        self.api.can_approve = True
        await self.assert_identity_rejected()


if __name__ == "__main__":
    unittest.main()
