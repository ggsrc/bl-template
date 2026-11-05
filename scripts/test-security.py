#!/usr/bin/env python3
"""Offline security regressions. All generated files and fake config stay in workspace/."""
import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class SecurityTemplates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.chdir(ROOT)
        Path("workspace").mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix="security-", dir="workspace")
        cls.work = Path(cls.temp.name).resolve()
        tools = cls.work / "bin"
        tools.mkdir()
        # Do not let blcli install tools or call a real kubectl/terraform.
        for tool in ["kubectl", "terraform", "istioctl"]:
            p = tools / tool
            p.write_text("#!/bin/sh\nexit 97\n")
            p.chmod(0o755)
        cls.blcli = shutil.which("blcli")
        if not cls.blcli:
            raise RuntimeError("install blcli before running these tests")
        # Subprocess-only home/config: never read or change the caller's environment.
        cls.env = {
            "PATH": str(tools) + os.pathsep + os.environ["PATH"],
            "HOME": str(cls.work / "home"),
            "KUBECONFIG": str(cls.work / "kubeconfig"),
            "BLCLI_KEYS_DIR": str(cls.work / "keys"),
            "HELM_REPOSITORY_CONFIG": str(cls.work / "repositories.yaml"),
            "HELM_REPOSITORY_CACHE": str(cls.work / "helm-cache"),
            "HELM_CACHE_HOME": str(cls.work / "helm-cache"),
            "HELM_CONFIG_HOME": str(cls.work / "helm-config"),
            "HELM_DATA_HOME": str(cls.work / "helm-data"),
        }
        Path(cls.env["HOME"]).mkdir()
        Path(cls.env["KUBECONFIG"]).write_text('apiVersion: v1\nkind: Config\nclusters: []\ncontexts: []\nusers: []\n')
        Path(cls.env["HELM_REPOSITORY_CONFIG"]).write_text('repositories: []\n')
        cls.run_command([cls.blcli, "init-args", str(ROOT), "-o", str(cls.work / "args.yaml")])
        args = yaml.safe_load((cls.work / "args.yaml").read_text())
        args["kubernetes"]["projects"] = [{"name": "security", "components": [
            {"name": name, "parameters": {}} for name in ["n9e", "uptrace", "bytebase"]
        ]}]
        cls.args = args
        cls.charts = cls.generate("default", args)
        cls.docs = {n: cls.render(p, n) for n, p in cls.charts.items()}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def run_command(cls, command, success=True):
        p = subprocess.run(command, env=cls.env, text=True, capture_output=True, timeout=60)
        if success and p.returncode:
            # Rendered output can contain generated test secrets; never log it.
            raise AssertionError(f"{command[0:2]} failed: {p.stderr[:2000]}")
        return p

    @classmethod
    def generate(cls, name, args):
        f = cls.work / f"{name}-args.yaml"
        f.write_text(yaml.safe_dump(args, sort_keys=False))
        output = cls.work / name
        cls.run_command([cls.blcli, "init", str(ROOT), "--no-resume", "--args", str(f), "--output", str(output), "--modules", "kubernetes"])
        paths = {n: output / "kubernetes/security" / n for n in ["n9e", "uptrace", "bytebase"]}
        for n in ["n9e", "uptrace"]:
            cls.run_command(["helm", "dependency", "build", "--skip-refresh", str(paths[n])])
        return paths

    @classmethod
    def render(cls, path, release, *extra):
        p = cls.run_command(["helm", "template", release, str(path), "--namespace", "security", "-f", str(path / "values-override.yaml"), *extra])
        return [d for d in yaml.safe_load_all(p.stdout) if d]

    @staticmethod
    def find(docs, kind, name=None):
        return next(d for d in docs if d["kind"] == kind and (name is None or d["metadata"]["name"] == name))

    def test_no_public_entry_or_node_access(self):
        for docs in self.docs.values():
            for d in docs:
                self.assertNotEqual(d["kind"], "Ingress")
                if d["kind"] == "Service":
                    self.assertEqual(d["spec"].get("type", "ClusterIP"), "ClusterIP")
                if d["kind"] in ["Deployment", "StatefulSet", "DaemonSet"]:
                    spec = d["spec"]["template"]["spec"]
                    self.assertFalse(spec.get("hostNetwork", False))
                    self.assertFalse(spec.get("automountServiceAccountToken", True))
                    self.assertFalse(any("hostPath" in v for v in spec.get("volumes", [])))
                    self.assertFalse(any(c.get("securityContext", {}).get("privileged") for c in spec["containers"]))

    def test_n9e_passwords_match_consumers(self):
        docs = self.docs["n9e"]
        data = self.find(docs, "Secret", "n9e-bootstrap")["data"]
        decoded = {k: base64.b64decode(v).decode() for k, v in data.items()}
        self.assertEqual(len(set(decoded.values())), 4)
        self.assertEqual(len(decoded["admin-password"]), 24)
        self.assertTrue(all(len(v) == 48 and v.isalnum() for k, v in decoded.items() if k != "admin-password"))
        config = self.find(docs, "Secret", "n9e-config")["stringData"]["config.toml"]
        self.assertIn(decoded["mysql-password"], config)
        self.assertIn(decoded["redis-password"], config)
        seed = self.find(docs, "Secret", "database-initdb-config")["stringData"]["a-n9e.sql"]
        self.assertIn(decoded["admin-password"], seed)
        mysql = next(d for d in docs if d["kind"] == "Secret" and "MYSQL_ROOT_PASSWORD" in d.get("stringData", {}))["stringData"]
        self.assertEqual(mysql["MYSQL_ROOT_PASSWORD"], decoded["mysql-root-password"])
        self.assertEqual(mysql["MYSQL_PASSWORD"], decoded["mysql-password"])
        self.assertEqual(mysql["MYSQL_USER"], "n9e")
        self.assertEqual(mysql["MYSQL_DATABASE"], "n9e_v6")
        self.assertNotIn("WITH GRANT OPTION", seed)
        redis = next(d for d in docs if d["kind"] == "StatefulSet" and d["spec"]["template"]["spec"]["containers"][0]["name"] == "redis")
        self.assertIn("--requirepass", redis["spec"]["template"]["spec"]["containers"][0]["args"])
        text = yaml.safe_dump(docs)
        for bad in ["root.2020", "__BLCLI_ADMIN_PASSWORD__", ":5.7", "categraf:latest"]:
            self.assertTrue(bad not in text, f"known default remains: {bad}")

    def test_uptrace_seeds_and_clickhouse_match(self):
        docs = self.docs["uptrace"]
        data = {k: base64.b64decode(v).decode() for k, v in self.find(docs, "Secret", "uptrace-bootstrap")["data"].items()}
        config = yaml.safe_load(self.find(docs, "Secret", "uptrace")["stringData"]["uptrace.yml"])
        self.assertEqual(config["service"]["secret"], data["service-secret"])
        self.assertEqual(config["seed_data"]["users"][0]["password"], data["admin-password"])
        self.assertEqual(config["seed_data"]["project_tokens"][0]["token"], data["project-token"])
        self.assertEqual(config["seed_data"]["user_tokens"][0]["token"], data["user-token"])
        users = self.find(docs, "ClickHouseInstallation")["spec"]["configuration"]["users"]
        self.assertEqual(users["uptrace/password_sha256_hex"], hashlib.sha256(data["clickhouse-password"].encode()).hexdigest())
        self.assertNotIn("::/0", users["uptrace/networks/ip"])
        text = yaml.safe_dump(docs)
        for bad in ["FIXME", "project1_secret", "user1_secret"]:
            self.assertTrue(bad not in text, f"known default remains: {bad}")
        sts = self.find(docs, "StatefulSet")
        env = sts["spec"]["template"]["spec"]["containers"][0]["env"]
        self.assertEqual(next(x for x in env if x["name"] == "CH_PASSWORD")["valueFrom"]["secretKeyRef"]["key"], "clickhouse-password")

    def test_bytebase_external_db_and_nonroot(self):
        docs = self.docs["bytebase"]
        spec = self.find(docs, "StatefulSet")["spec"]["template"]["spec"]
        self.assertTrue(spec["securityContext"]["runAsNonRoot"])
        self.assertEqual(spec["securityContext"]["runAsUser"], 113)
        c = spec["containers"][0]
        self.assertTrue(c["securityContext"]["readOnlyRootFilesystem"])
        self.assertFalse(c["securityContext"]["allowPrivilegeEscalation"])
        self.assertEqual(c["securityContext"]["capabilities"]["drop"], ["ALL"])
        self.assertNotIn("--disable-sample", c["args"])
        pg = next(x for x in c["env"] if x["name"] == "PG_URL")
        self.assertEqual(pg["valueFrom"]["secretKeyRef"]["name"], "bytebase-postgresql-app")
        self.assertFalse(self.find(docs, "Cluster")["spec"]["enableSuperuserAccess"])
        self.assertEqual(self.find(docs, "NetworkPolicy")["spec"]["ingress"], [])

    def test_nondefault_args_survive_blcli_and_helm(self):
        args = json.loads(json.dumps(self.args))
        components = args["kubernetes"]["projects"][0]["components"]
        components[0]["parameters"] = {"imageTag": "9.1.2-test", "prometheusPort": "9999"}
        components[1]["parameters"] = {"imageTag": "2.0.2-test", "replicaCount": 3, "clickhouseAllowedCIDR": "172.16.0.0/12"}
        components[2]["parameters"] = {"metadataDatabaseEnabled": False, "existingPgURLSecret": "test-uri", "existingPgURLSecretKey": "connection"}
        paths = self.generate("custom", args)
        n = self.render(paths["n9e"], "n9e")
        self.assertIn("flashcatcloud/nightingale:9.1.2-test", yaml.safe_dump(n))
        self.assertIn(":9999/api/v1/write", self.find(n, "Secret", "n9e-config")["stringData"]["config.toml"])
        u = self.render(paths["uptrace"], "uptrace")
        self.assertEqual(self.find(u, "StatefulSet")["spec"]["replicas"], 3)
        self.assertIn("uptrace/uptrace:2.0.2-test", yaml.safe_dump(u))
        self.assertEqual(self.find(u, "ClickHouseInstallation")["spec"]["configuration"]["users"]["uptrace/networks/ip"], ["172.16.0.0/12"])
        b = self.render(paths["bytebase"], "bytebase")
        self.assertFalse(any(x["kind"] == "Cluster" for x in b))
        env = self.find(b, "StatefulSet")["spec"]["template"]["spec"]["containers"][0]["env"]
        self.assertEqual(next(x for x in env if x["name"] == "PG_URL")["valueFrom"]["secretKeyRef"], {"name": "test-uri", "key": "connection"})

    def test_rejects_unsafe_bytebase_fallback(self):
        for values in ["metadataDatabase.enabled=false", "bytebase.version=3.1.0", "bytebase.option.externalPg.pgPassword=unsafe"]:
            p = self.run_command(["helm", "template", "bytebase", str(self.charts["bytebase"]), "--set", values], success=False)
            self.assertNotEqual(p.returncode, 0)

    def test_upgrade_without_credentials_fails(self):
        for n in ["n9e", "uptrace"]:
            p = self.run_command(["helm", "template", n, str(self.charts[n]), "--is-upgrade"], success=False)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("bootstrap Secret missing", p.stderr)

    def test_lint_and_installer_syntax(self):
        for name, path in self.charts.items():
            self.run_command(["helm", "lint", "--strict", str(path)])
            self.run_command(["bash", "-n", str(path / "install")])

    def test_installer_gate_prevents_mutations(self):
        fake = self.work / "installer-bin"
        fake.mkdir()
        for name, path in self.charts.items():
            log = self.work / f"{name}-commands.log"
            helm = fake / "helm"
            helm.write_text(f'#!/bin/sh\nprintf "%s\\n" "$1" >> "{log}"\nif [ "$1" = list ]; then printf "%s\\n" "{name}"; else exit 97; fi\n')
            helm.chmod(0o755)
            env = dict(self.env, PATH=str(fake) + os.pathsep + self.env["PATH"])
            p = subprocess.run(["bash", "./install"], cwd=path, env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("BLCLI_SECURITY_MIGRATION_APPROVED", p.stdout)
            self.assertEqual(log.read_text().splitlines(), ["list"])

    def test_upgrade_lookup_retains_actual_secret(self):
        secrets = {n + "-bootstrap": self.find(self.docs[n], "Secret", n + "-bootstrap") for n in ["n9e", "uptrace"]}

        class API(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                path = self.path.split("?")[0]
                if path == "/version":
                    body = {"major": "1", "minor": "31", "gitVersion": "v1.31.0"}
                elif path == "/api":
                    body = {"kind": "APIVersions", "versions": ["v1"]}
                elif path == "/apis":
                    body = {"kind": "APIGroupList", "apiVersion": "v1", "groups": []}
                elif path == "/api/v1":
                    body = {"kind": "APIResourceList", "groupVersion": "v1", "resources": [{"name": "secrets", "kind": "Secret", "namespaced": True, "verbs": ["get", "list"]}]}
                elif path.startswith("/api/v1/namespaces/security/secrets/"):
                    body = secrets[path.rsplit("/", 1)[1]]
                else:
                    self.send_error(404)
                    return
                raw = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), API)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config = self.work / "fake-server-kubeconfig"
        config.write_text(yaml.safe_dump({"apiVersion": "v1", "kind": "Config", "clusters": [{"name": "test", "cluster": {"server": f"http://127.0.0.1:{server.server_port}"}}], "contexts": [{"name": "test", "context": {"cluster": "test", "user": "test"}}], "users": [{"name": "test", "user": {}}], "current-context": "test"}))
        try:
            for n in ["n9e", "uptrace"]:
                docs = self.render(self.charts[n], n, "--is-upgrade", "--dry-run=server", "--kubeconfig", str(config))
                self.assertEqual(self.find(docs, "Secret", n + "-bootstrap")["data"], secrets[n + "-bootstrap"]["data"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main(verbosity=2)
