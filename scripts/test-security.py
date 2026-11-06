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
import sys
import tempfile
import threading
import tomllib
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

    def test_n9e_heartbeat_uses_pod_ip_without_public_probe(self):
        docs = self.docs["n9e"]
        config = self.find(docs, "Secret", "n9e-config")["stringData"]["config.toml"]
        self.assertNotIn("IP", tomllib.loads(config)["Alert"]["Heartbeat"])
        deployment = next(d for d in docs if d["kind"] == "Deployment" and d["spec"]["template"]["spec"]["containers"][0]["name"] == "center")
        env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
        self.assertEqual(next(x for x in env if x["name"] == "CONFIGTYPE_ALERT_HEARTBEAT_IP")["valueFrom"]["fieldRef"]["fieldPath"], "status.podIP")

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

    def test_installer_version_gate_and_failed_install_retry(self):
        fake = self.work / "installer-bin"
        fake.mkdir()
        log = self.work / "installer-commands.log"
        helm = fake / "helm"
        helm.write_text(f"#!{sys.executable}\n" + """import json, os, re, sys
with open(os.environ['FAKE_LOG'], 'a') as f:
    f.write(sys.argv[1] + '\\n')
if sys.argv[1] == 'list':
    assert sys.argv[sys.argv.index('--filter') + 1] == '^' + re.escape(os.environ['FAKE_EXPECTED_RELEASE']) + '$'
    print(os.environ['FAKE_RELEASES'])
    sys.exit(int(os.environ.get('FAKE_LIST_EXIT', '0')))
# Stop before any writes: reaching dependency means the version gate passed.
sys.exit(97)
""")
        helm.chmod(0o755)
        kubectl = fake / "kubectl"
        kubectl.write_text('#!/bin/sh\nif [ "$1" = get ] && [ "$2" = crd ]; then exit 0; fi\nexit 97\n')
        kubectl.chmod(0o755)
        for name, path in self.charts.items():
            row = lambda chart, status="deployed", release=name: {"name": release, "chart": chart, "status": status}
            cases = [
                ("fresh", [], False, True),
                ("legacy", [row(name + "-1.0.0")], False, False),
                ("legacy-approved", [row(name + "-1.1.1")], True, True),
                ("current", [row(name + "-2.0.0")], False, True),
                ("patch-upgrade", [row(name + "-2.0.1")], False, True),
                ("failed-new-retry", [row(name + "-2.0.0", "failed")], False, True),
                ("failed-old-retry", [row(name + "-1.0.0", "failed")], False, False),
                ("exact-name", [row(name + "-1.0.0", release=name + "-other")], False, True),
                ("unknown-chart", [row("other-2.0.0")], True, False),
                ("malformed-version", [row(name + "-nonsense")], True, False),
                ("duplicates", [row(name + "-1.0.0"), row(name + "-2.0.0")], True, False),
                ("malformed-row", ["bad"], True, False),
                ("malformed-list", {}, True, False),
            ]
            for title, rows, approved, passed in cases:
                with self.subTest(component=name, scenario=title):
                    log.write_text("")
                    env = dict(self.env, PATH=str(fake) + os.pathsep + self.env["PATH"],
                               FAKE_LOG=str(log), FAKE_RELEASES=json.dumps(rows), FAKE_EXPECTED_RELEASE=name)
                    if approved:
                        env["BLCLI_SECURITY_MIGRATION_APPROVED"] = "1"
                    result = subprocess.run(["bash", "./install"], cwd=path, env=env, capture_output=True, text=True, timeout=10)
                    self.assertNotEqual(result.returncode, 0)  # fake helm stops at dependency
                    self.assertEqual(log.read_text().splitlines(), ["list", "dependency"] if passed else ["list"])
            # A failed API read must not look like a first installation, even with approval.
            for output in ["[]", "not-json"]:
                log.write_text("")
                env = dict(self.env, PATH=str(fake) + os.pathsep + self.env["PATH"],
                           FAKE_LOG=str(log), FAKE_RELEASES=output, FAKE_EXPECTED_RELEASE=name, FAKE_LIST_EXIT="1",
                           BLCLI_SECURITY_MIGRATION_APPROVED="1")
                result = subprocess.run(["bash", "./install"], cwd=path, env=env, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(log.read_text().splitlines(), ["list"])

    def test_n9e_allows_monitoring_query_and_write_only(self):
        policy = self.find(self.docs["n9e"], "NetworkPolicy")["spec"]
        rules = [rule for rule in policy["egress"] if any(
            peer.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name") == "monitoring-vm"
            for peer in rule.get("to", []))]
        self.assertEqual(len(rules), 1)
        self.assertEqual({(p["protocol"], p["port"]) for p in rules[0]["ports"]}, {("TCP", 8429), ("TCP", 8481)})
        self.assertTrue(all(rule.get("to") and rule.get("ports") for rule in rules))

    def test_nginx_privileges_and_immutable_images(self):
        deployment = next(d for d in self.docs["n9e"] if d["kind"] == "Deployment" and d["spec"]["template"]["spec"]["containers"][0]["name"] == "nginx")
        spec = deployment["spec"]["template"]["spec"]
        container = spec["containers"][0]
        self.assertTrue(spec["securityContext"]["runAsNonRoot"])
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        self.assertFalse(container["securityContext"]["allowPrivilegeEscalation"])
        self.assertEqual(container["securityContext"]["capabilities"]["drop"], ["ALL"])
        self.assertIn({"name": "nginx-tmp", "mountPath": "/tmp"}, container["volumeMounts"])
        self.assertRegex(container["image"], r"nginx:[0-9]+\.[0-9]+\.[0-9]+-alpine@sha256:[a-f0-9]{64}$")
        clickhouse = self.find(self.docs["uptrace"], "ClickHouseInstallation")
        image = clickhouse["spec"]["templates"]["podTemplates"][0]["spec"]["containers"][0]["image"]
        self.assertRegex(image, r"clickhouse/clickhouse-server:25\.3\.[0-9]+\.[0-9]+@sha256:[a-f0-9]{64}$")
        override = self.render(self.charts["uptrace"], "uptrace", "--set", "uptrace.clickhouse.image.tag=25.3.14.14-test")
        self.assertIn("clickhouse/clickhouse-server:25.3.14.14-test", yaml.safe_dump(override))

    def test_bytebase_removed_parameters_are_not_advertised(self):
        old = ["externalPgEnable", "pgHost", "pgPort", "pgUsername", "pgDatabase", "existingPgPasswordSecret", "existingPgPasswordSecretKey"]
        args = yaml.safe_load((ROOT / "kubernetes/components/bytebase/args.yaml").read_text())["parameters"]["components"]["bytebase"]
        for name in old:
            self.assertNotIn(name, args)
            self.assertNotIn("." + name, (ROOT / "kubernetes/components/bytebase/values-override.yaml.tmpl").read_text())
        for value in ["bytebase.option.externalPg.enable=false", "bytebase.option.externalPg.pgDatabase=old", "bytebase.option.disable-sample=true"]:
            result = self.run_command(["helm", "template", "bytebase", str(self.charts["bytebase"]), "--set", value], success=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("removed", result.stderr)

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
