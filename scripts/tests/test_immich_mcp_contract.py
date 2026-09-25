#!/usr/bin/env python3
"""Contract tests: Immich MCP is first-class in fragments, install, and validate."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRAG = ROOT / "mcp" / "fragments"
SCRIPTS = ROOT / "scripts"
DOCS = ROOT / "mcp" / "README.md"


class ImmichFragmentContractTests(unittest.TestCase):
    def test_codex_fragment_registers_immich(self) -> None:
        text = (FRAG / "codex.homelab-mcp.toml").read_text(encoding="utf-8")
        self.assertIn("[mcp_servers.immich]", text)
        self.assertIn("immich-mcp.archer.casa/mcp", text)
        self.assertIn("startup_timeout_sec", text)

    def test_grok_fragment_registers_immich_http(self) -> None:
        text = (FRAG / "grok.homelab-mcp.toml").read_text(encoding="utf-8")
        self.assertIn("[mcp_servers.immich]", text)
        self.assertIn("immich-mcp.archer.casa/mcp", text)
        self.assertIn("startup_timeout_sec", text)
        # Paperless remains stdio for Grok
        self.assertIn("@baruchiro/paperless-mcp", text)

    def test_gemini_fragment_registers_immich(self) -> None:
        data = json.loads((FRAG / "gemini.mcpServers.json").read_text(encoding="utf-8"))
        self.assertIn("immich", data)
        self.assertIn("paperless", data)
        self.assertIn("/mcp", data["immich"]["url"])
        self.assertIn("timeout", data["immich"])

    def test_antigravity_fragment_registers_immich(self) -> None:
        data = json.loads((FRAG / "antigravity.mcp_config.json").read_text(encoding="utf-8"))
        servers = data["mcpServers"]
        self.assertIn("immich", servers)
        self.assertIn("paperless", servers)
        self.assertIn("immich-mcp.archer.casa/mcp", servers["immich"]["url"])

    def test_omp_fragment_registers_immich(self) -> None:
        data = json.loads((FRAG / "omp.mcpServers.json").read_text(encoding="utf-8"))
        self.assertIn("immich", data)
        self.assertIn("paperless", data)
        self.assertIn("immich-mcp.archer.casa/mcp", data["immich"]["url"])


class ImmichBootstrapContractTests(unittest.TestCase):
    def test_install_script_registers_immich_for_clients(self) -> None:
        text = (SCRIPTS / "install-homelab-mcp.ps1").read_text(encoding="utf-8")
        self.assertIn("Resolve-ImmichMcpUrl", text)
        self.assertIn("codex mcp add immich", text)
        self.assertIn("grok mcp add --transport http immich", text)
        self.assertIn("immich", text.lower())
        # DNS / Tailscale fallback path
        self.assertIn("HOMELAB_TRAEFIK_TS_IP", text)
        self.assertIn("UseHostHeader", text)
        self.assertIn('codex mcp add immich --url $immich.Url --header "Host: $($immich.HostHeader)"', text)

    def test_setup_agents_sh_registers_immich(self) -> None:
        text = (SCRIPTS / "setup_agents.sh").read_text(encoding="utf-8")
        self.assertIn("codex mcp add immich", text)
        self.assertIn("grok mcp add --transport http immich", text)
        self.assertIn("immich-mcp.archer.casa", text)
        self.assertIn("HOMELAB_TRAEFIK_TS_IP", text)
        self.assertIn('codex mcp add immich --url "$immich_url" --header "Host: ${immich_host}"', text)

    def test_setup_agents_sh_codex_host_header_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mock_bin = os.path.join(td, "codex")
            log_file = os.path.join(td, "codex.log")
            with open(mock_bin, "w", encoding="utf-8") as f:
                f.write(f"""#!/bin/sh
echo "$@" >> "{log_file}"
exit 0
""")
            os.chmod(mock_bin, 0o755)

            script = f"""
            export PATH="{td}:$PATH"
            export HOME="{td}"
            export REPO_ROOT="{ROOT}"
            eval "$(sed '/^main /d' "{SCRIPTS / 'setup_agents.sh'}")"
            getent() {{ return 1; }}
            host() {{ return 1; }}
            nslookup() {{ return 1; }}
            log() {{ :; }}
            install_mcp_clients
            """
            proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, f"Script failed: {proc.stderr}")
            with open(log_file, encoding="utf-8") as f:
                calls = f.read()
            self.assertIn(
                "mcp add immich --url http://100.68.151.94/mcp --header Host: immich-mcp.archer.casa",
                calls,
            )

    def test_setup_agents_sh_codex_host_header_fallback_on_unsupported_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mock_bin = os.path.join(td, "codex")
            log_file = os.path.join(td, "codex.log")
            with open(mock_bin, "w", encoding="utf-8") as f:
                f.write(f"""#!/bin/sh
echo "$@" >> "{log_file}"
for arg in "$@"; do
    if [ "$arg" = "--header" ]; then
        echo "error: unexpected argument '--header' found" >&2
        exit 2
    fi
done
exit 0
""")
            os.chmod(mock_bin, 0o755)

            script = f"""
            export PATH="{td}:$PATH"
            export HOME="{td}"
            export REPO_ROOT="{ROOT}"
            eval "$(sed '/^main /d' "{SCRIPTS / 'setup_agents.sh'}")"
            getent() {{ return 1; }}
            host() {{ return 1; }}
            nslookup() {{ return 1; }}
            log() {{ :; }}
            install_mcp_clients
            """
            proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, f"Script failed: {proc.stderr}")
            with open(log_file, encoding="utf-8") as f:
                calls = f.read().splitlines()
            self.assertIn(
                "mcp add immich --url http://100.68.151.94/mcp --header Host: immich-mcp.archer.casa",
                calls,
            )
            self.assertIn(
                "mcp add immich --url http://100.68.151.94/mcp",
                calls,
            )


class ImmichValidateContractTests(unittest.TestCase):
    def test_ps1_has_timed_client_probe_and_actionable_failures(self) -> None:
        text = (SCRIPTS / "validate-homelab-mcp.ps1").read_text(encoding="utf-8")
        self.assertIn("Test-ImmichClientReachability", text)
        self.assertIn("Invoke-TimedHttpGet", text)
        self.assertIn("TimeoutSec", text)
        self.assertIn("/health", text)
        self.assertIn("/mcp", text)
        # Actionable failure modes (not silent hang)
        self.assertIn("timed out", text.lower())
        self.assertIn("allowlist", text.lower())
        self.assertIn("192.168.0.0/16", text)
        self.assertIn("100.64.0.0/10", text)
        self.assertIn("handshake", text.lower())
        # Bounds kubectl / curl hangs
        self.assertRegex(text, re.compile(r"request-timeout|Timeout\s*=", re.I))

    def test_sh_has_timed_client_probe_and_actionable_failures(self) -> None:
        path = SCRIPTS / "validate-homelab-mcp.sh"
        self.assertTrue(path.is_file(), "validate-homelab-mcp.sh must exist for Unix parity")
        text = path.read_text(encoding="utf-8")
        self.assertIn("probe_immich", text)
        self.assertIn("TIMEOUT_SEC", text)
        self.assertIn("/health", text)
        self.assertIn("allowlist", text.lower())
        self.assertIn("192.168.0.0/16", text)
        self.assertIn("100.64.0.0/10", text)
        self.assertIn("handshake", text.lower())
        # curl max-time present (avoids silent hangs)
        self.assertTrue(
            re.search(r"curl[^\n]*-m\s|curl[^\n]*--max-time", text) or "-m " in text,
            "Unix validate must pass a curl max-time to avoid hangs",
        )


class ImmichDocsContractTests(unittest.TestCase):
    def test_mcp_readme_covers_allowlist_and_failure_modes(self) -> None:
        text = DOCS.read_text(encoding="utf-8")
        self.assertIn("192.168.0.0/16", text)
        self.assertIn("100.64.0.0/10", text)
        self.assertIn("allowlist", text.lower())
        self.assertIn("failure modes", text.lower())
        self.assertIn("validate-homelab-mcp", text)
        self.assertIn("silent hang", text.lower())
        self.assertIn("HOMELAB_TRAEFIK_TS_IP", text)


if __name__ == "__main__":
    unittest.main()
