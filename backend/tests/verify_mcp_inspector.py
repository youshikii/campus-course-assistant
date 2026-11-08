r"""Explicit Inspector CLI acceptance, isolated from real DB and credentials.

Run from backend: .venv\Scripts\python.exe tests/verify_mcp_inspector.py
Install the pinned dev tool first: npm ci --prefix tools/mcp-inspector
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_campus import CampusIntegrationTests

BACKEND = Path(__file__).resolve().parents[1]
LAUNCHER = BACKEND / "tools/mcp-inspector/node_modules/@modelcontextprotocol/inspector/clients/launcher/build/index.js"


def main():
    if not LAUNCHER.is_file() or not shutil.which("node"):
        raise SystemExit("Install Node and run npm ci --prefix tools/mcp-inspector first")
    fixture = CampusIntegrationTests()
    CampusIntegrationTests.setUpClass()
    try:
        fixture.setUp()
        course = fixture.create_course()
        fixture.create_schedule(course["id"])
        with tempfile.TemporaryDirectory(prefix="campus-inspector-") as folder:
            config = Path(folder) / "mcp.json"
            environment = {**os.environ, "MCP_AUTO_OPEN_ENABLED": "false",
                           "MCP_INSPECTOR_SECRET_STORE": "memory", "MCP_STORAGE_DIR": folder}

            def invoke(token, method, *args, exit_code=0):
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                config.write_text(json.dumps({"mcpServers": {"campus": {
                    "type": "http", "url": fixture.mcp_url, "headers": headers,
                }}}), encoding="utf-8")
                result = subprocess.run([
                    shutil.which("node"), str(LAUNCHER), "--cli", "--config", str(config),
                    "--server", "campus", "--stored-auth-only", "--format", "json",
                    "--method", method, *args,
                ], env=environment, capture_output=True, text=True, encoding="utf-8", timeout=45)
                if result.returncode != exit_code:
                    diagnostic = result.stderr.replace(token, "[REDACTED]") if token else result.stderr
                    raise AssertionError(f"Inspector exit {result.returncode}: {diagnostic}")
                return json.loads(result.stdout) if result.stdout.strip() else None

            invoke("", "tools/list", exit_code=3)
            print("Inspector: missing login token rejected (401)")
            for username, password, expected in (("alice", "alice123", 1), ("bob", "bob123", 0)):
                response = fixture.client.post("/api/auth/login", json={"username": username, "password": password})
                token = response.json()["data"]["token"]
                discovery = invoke(token, "tools/list")["result"]
                tool = next(tool for tool in discovery["tools"] if tool["name"] == "get_my_schedules")
                assert set(tool["inputSchema"]["properties"]) == {"on_date"}
                for day, count in ((None, expected), ("2026-10-22", expected), ("2026-10-23", 0), ("2027-02-04", 0)):
                    args = ["--tool-name", "get_my_schedules"]
                    if day:
                        args += ["--tool-arg", f"on_date={day}"]
                    result = invoke(token, "tools/call", *args)["result"]
                    assert not result.get("isError"), result
                    data = result.get("structuredContent")
                    if data is None:
                        data = json.loads("".join(block.get("text", "") for block in result["content"]))
                    assert data["total"] == count and len(data["schedules"]) == count, data
                    print(f"Inspector: {username}, date={day or 'all'}, total={count} OK")
            print("Inspector acceptance passed; temporary tokens/config/database removed on exit.")
    finally:
        CampusIntegrationTests.tearDownClass()


if __name__ == "__main__":
    main()
