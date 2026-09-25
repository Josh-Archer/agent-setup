#!/usr/bin/env python3
"""Contract tests: Immich MCP is first-class in fragments, install, and validate."""

from __future__ import annotations

import json
import os
import re
import shutil
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
        self.assertIn("codex mcp add immich --url $immich.Url", text)
        self.assertNotIn("codex mcp add immich --url $immich.Url --header", text)
        self.assertIn("Set-CodexImmichHostHeader", text)

    def test_setup_agents_sh_registers_immich(self) -> None:
        text = (SCRIPTS / "setup_agents.sh").read_text(encoding="utf-8")
        self.assertIn("codex mcp add immich", text)
        self.assertIn("grok mcp add --transport http immich", text)
        self.assertIn("immich-mcp.archer.casa", text)
        self.assertIn("HOMELAB_TRAEFIK_TS_IP", text)
        self.assertIn('codex mcp add immich --url "$immich_url"', text)
        self.assertNotIn('codex mcp add immich --url "$immich_url" --header', text)
        self.assertIn("set_codex_immich_host_header", text)

    def test_setup_agents_sh_codex_host_header_fallback_mock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mock_codex = os.path.join(td, "codex")
            log_file = os.path.join(td, "codex.log")
            with open(mock_codex, "w", encoding="utf-8") as f:
                f.write(f"""#!/bin/sh
echo "$@" >> "{log_file}"
if [ "$1" = "mcp" ] && [ "$2" = "add" ]; then
    cfg="${{CODEX_HOME:-$HOME/.codex}}/config.toml"
    mkdir -p "$(dirname "$cfg")"
    name="$3"
    url="$5"
    printf '[mcp_servers.%s]\\nurl = "%s"\\n' "$name" "$url" >> "$cfg"
elif [ "$1" = "mcp" ] && [ "$2" = "remove" ]; then
    cfg="${{CODEX_HOME:-$HOME/.codex}}/config.toml"
    if [ -f "$cfg" ]; then
        name="$3"
        python3 -c "
import sys, re
c_path, n = sys.argv[1], sys.argv[2]
with open(c_path, 'r', encoding='utf-8') as fh: c = fh.read()
p = r'(?ms)^\\[mcp_servers\\.' + re.escape(n) + r'\\]\\r?\\n.*?(?=(?:^\\[|\\Z))'
with open(c_path, 'w', encoding='utf-8') as fh: fh.write(re.sub(p, '', c))
" "$cfg" "$name" 2>/dev/null || true
    fi
fi
exit 0
""")
            os.chmod(mock_codex, 0o755)

            # Stub out other CLIs so they don't run for real
            for stub in ["grok", "claude", "powershell.exe", "pwsh"]:
                stub_path = os.path.join(td, stub)
                with open(stub_path, "w", encoding="utf-8") as f:
                    f.write("#!/bin/sh\nexit 0\n")
                os.chmod(stub_path, 0o755)

            def run_install(dns_ok: bool) -> subprocess.CompletedProcess[str]:
                dns_ret = "0" if dns_ok else "1"
                script = f"""
                export PATH="{td}:$PATH"
                export HOME="{td}"
                export CODEX_HOME="{td}"
                . "{SCRIPTS / 'setup_agents.sh'}"
                getent() {{ return {dns_ret}; }}
                host() {{ return {dns_ret}; }}
                nslookup() {{ return {dns_ret}; }}
                log() {{ :; }}
                install_mcp_clients
                """
                return subprocess.run(["bash", "-c", script], capture_output=True, text=True)

            # 1. DNS fallback run
            proc = run_install(dns_ok=False)
            self.assertEqual(proc.returncode, 0, f"Script failed: {proc.stderr}")
            with open(log_file, encoding="utf-8") as f:
                calls = f.read()
            self.assertIn("mcp add immich --url http://100.68.151.94/mcp", calls)
            self.assertNotIn("--header", calls)

            cfg_file = os.path.join(td, "config.toml")
            self.assertTrue(os.path.isfile(cfg_file))
            with open(cfg_file, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[mcp_servers.immich]", content)
            self.assertIn('http_headers = { Host = "immich-mcp.archer.casa" }', content)

            # 2. Re-run: verify idempotency (no duplicate http_headers)
            proc_rerun = run_install(dns_ok=False)
            self.assertEqual(proc_rerun.returncode, 0, f"Re-run failed: {proc_rerun.stderr}")
            with open(cfg_file, encoding="utf-8") as f:
                content_rerun = f.read()
            self.assertEqual(content_rerun.count("http_headers"), 1)
            self.assertEqual(content_rerun.count("[mcp_servers.immich]"), 1)

            # 3. DNS-ok path: verify no header added
            proc_dns_ok = run_install(dns_ok=True)
            self.assertEqual(proc_dns_ok.returncode, 0, f"DNS ok run failed: {proc_dns_ok.stderr}")
            with open(cfg_file, encoding="utf-8") as f:
                content_dns_ok = f.read()
            self.assertIn('url = "http://immich-mcp.archer.casa/mcp"', content_dns_ok)
            self.assertNotIn("http_headers", content_dns_ok)

    def test_setup_agents_sh_codex_host_header_fallback_real_cli(self) -> None:
        codex_bin = shutil.which("codex")
        if not codex_bin:
            self.skipTest("codex CLI not available in environment")

        with tempfile.TemporaryDirectory() as td:
            stubs_dir = os.path.join(td, "stubs")
            os.makedirs(stubs_dir, exist_ok=True)
            for stub in ["grok", "claude", "powershell.exe", "pwsh"]:
                stub_path = os.path.join(stubs_dir, stub)
                with open(stub_path, "w", encoding="utf-8") as f:
                    f.write("#!/bin/sh\nexit 0\n")
                os.chmod(stub_path, 0o755)

            def run_install(dns_ok: bool) -> subprocess.CompletedProcess[str]:
                dns_ret = "0" if dns_ok else "1"
                script = f"""
                export PATH="{stubs_dir}:$PATH"
                export HOME="{td}"
                export CODEX_HOME="{td}"
                . "{SCRIPTS / 'setup_agents.sh'}"
                getent() {{ return {dns_ret}; }}
                host() {{ return {dns_ret}; }}
                nslookup() {{ return {dns_ret}; }}
                log() {{ :; }}
                install_mcp_clients
                """
                return subprocess.run(["bash", "-c", script], capture_output=True, text=True)

            # 1. DNS fallback path
            proc = run_install(dns_ok=False)
            self.assertEqual(proc.returncode, 0, f"Script failed: {proc.stderr}")

            cfg_file = os.path.join(td, "config.toml")
            self.assertTrue(os.path.isfile(cfg_file))
            with open(cfg_file, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("[mcp_servers.immich]", content)
            self.assertIn('http_headers = { Host = "immich-mcp.archer.casa" }', content)

            env = os.environ.copy()
            env["CODEX_HOME"] = td
            env["HOME"] = td
            get_res = subprocess.run(
                ["codex", "mcp", "get", "immich", "--json"],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(get_res.stdout)
            self.assertIsNotNone(data.get("transport", {}).get("http_headers"))
            self.assertEqual(data["transport"]["http_headers"].get("Host"), "immich-mcp.archer.casa")

            # 2. Re-run: ensure idempotent and no duplicate keys
            proc_rerun = run_install(dns_ok=False)
            self.assertEqual(proc_rerun.returncode, 0, f"Re-run failed: {proc_rerun.stderr}")
            with open(cfg_file, encoding="utf-8") as f:
                content_rerun = f.read()
            self.assertEqual(content_rerun.count("http_headers"), 1)

            get_res2 = subprocess.run(
                ["codex", "mcp", "get", "immich", "--json"],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            data2 = json.loads(get_res2.stdout)
            self.assertEqual(data2["transport"]["http_headers"].get("Host"), "immich-mcp.archer.casa")

            # 3. DNS-ok path: no header
            proc_dns_ok = run_install(dns_ok=True)
            self.assertEqual(proc_dns_ok.returncode, 0, f"DNS-ok run failed: {proc_dns_ok.stderr}")
            with open(cfg_file, encoding="utf-8") as f:
                content_dns_ok = f.read()
            self.assertIn('url = "http://immich-mcp.archer.casa/mcp"', content_dns_ok)
            self.assertNotIn("http_headers", content_dns_ok)

            get_res3 = subprocess.run(
                ["codex", "mcp", "get", "immich", "--json"],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            data3 = json.loads(get_res3.stdout)
            self.assertIsNone(data3["transport"].get("http_headers"))


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
