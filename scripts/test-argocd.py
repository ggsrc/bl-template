#!/usr/bin/env python3
"""Offline ArgoCD component tests: render through blcli, run the generated scripts against fake
kubectl/kubeseal/curl, and check the fail-closed guards. Nothing talks to a cluster or the network;
all generated files stay in workspace/."""
import copy
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = "2-argocd"

# A stand-in for manifests/install.yaml: the objects kustomization.yaml patches must exist.
FAKE_MANIFEST = """\
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  labels:
    app.kubernetes.io/name: argocd-cm
    app.kubernetes.io/part-of: argocd
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cmd-params-cm
"""
FAKE_SHA256 = hashlib.sha256(FAKE_MANIFEST.encode()).hexdigest()

# Fake kubectl: logs every call, answers the read-only ones, never mutates anything.
FAKE_KUBECTL = """#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_LOG"
case "$*" in
  "cluster-info") exit 0 ;;
  "config current-context") echo test ;;
  "create secret"*) printf 'apiVersion: v1\\nkind: Secret\\nmetadata:\\n  name: %s\\n# %s\\n' "$4" "$*" ;;
  "label --local"*) cat; printf '# label %s\\n' "$*" ;;
  *"get configmap argocd-cm"*) printf '%s' "${FAKE_CM_REPOSITORIES:-}" ;;
  *"get secret"*) exit 1 ;;
esac
exit 0
"""
FAKE_CURL = """#!/bin/bash
printf 'curl %s\\n' "$*" >> "$FAKE_LOG"
while [ $# -gt 0 ]; do
  if [ "$1" = -o ]; then cp "$FAKE_MANIFEST_SOURCE" "$2"; fi
  shift
done
"""
FAKE_KUBESEAL = "#!/bin/sh\ncat\n"


class ArgoCDTemplates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.chdir(ROOT)
        Path("workspace").mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix="argocd-", dir="workspace")
        cls.work = Path(cls.temp.name).resolve()
        cls.blcli = shutil.which("blcli")
        if not cls.blcli:
            raise RuntimeError("install blcli before running these tests")
        cls.kustomize = shutil.which("kustomize")
        if not cls.kustomize and os.environ.get("CI"):
            raise RuntimeError("kustomize is required in CI (the GitHub ubuntu runner ships it)")
        tools = cls.work / "bin"
        tools.mkdir()
        for name, body in [("kubectl", FAKE_KUBECTL), ("curl", FAKE_CURL), ("kubeseal", FAKE_KUBESEAL)]:
            (tools / name).write_text(body)
            (tools / name).chmod(0o755)
        if not cls.kustomize:
            # Guards run after the tool check; a stub is enough for them.
            (tools / "kustomize").write_text("#!/bin/sh\nexit 97\n")
            (tools / "kustomize").chmod(0o755)
        for tool in ["terraform", "istioctl", "helm"]:
            (tools / tool).write_text("#!/bin/sh\nexit 97\n")
            (tools / tool).chmod(0o755)
        (cls.work / "manifest.yaml").write_text(FAKE_MANIFEST)
        cls.keys = cls.work / "keys"
        cls.env = {
            "PATH": str(tools) + os.pathsep + os.environ["PATH"],
            "HOME": str(cls.work / "home"),
            "KUBECONFIG": str(cls.work / "kubeconfig"),
            "BLCLI_KEYS_DIR": str(cls.keys),
            "FAKE_MANIFEST_SOURCE": str(cls.work / "manifest.yaml"),
        }
        Path(cls.env["HOME"]).mkdir()
        cls.run_command([cls.blcli, "init-args", str(ROOT), "-o", str(cls.work / "args.yaml")])
        cls.args = yaml.safe_load((cls.work / "args.yaml").read_text())
        cls.defaults = cls.generate("defaults", cls.args, modules=["kubernetes", "gitops"])

        # The single-environment default uses the local admin and an SSH deploy key. The full setup
        # (GitHub App credentials, GitHub SSO through Dex, RBAC) lives in examples/multi-env; the cases build on it.
        example = yaml.safe_load((ROOT / "examples/multi-env/kubernetes.default.yaml").read_text())
        base = next(c for c in example["projects"][0]["components"] if c["name"] == COMPONENT)["parameters"]
        app = dict(base, GitHubAppID="1", GitHubAppInstallationID="2",
                   ArgoCDManifestURL="https://example.invalid/install.yaml", ArgoCDManifestSHA256=FAKE_SHA256)
        no_dex = {k: v for k, v in app.items() if k != "dex-config"}
        ssh = dict(app, GitAuthMethod="ssh", GitRepositories=[
            {"url": "git@github.com:example-org/gitops.git", "name": "gitops", "sshPrivateKeyFile": "key_gitops"},
            {"url": "git@github.com:example-org/charts.git", "sshPrivateKeyFile": "key_charts"},
        ])
        cls.cases = {
            "enterprise": base,
            "app": app,
            "permissive": dict(app, RestrictDefaultProject=False),
            "ssh": ssh,
            "app-ssh-url": dict(app, GitRepositoryURL="git@github.com:example-org/gitops.git"),
            "ssh-https-url": dict(ssh, GitRepositories=[{"url": "https://github.com/example-org/gitops.git"}]),
            "no-sso": no_dex,
            "no-sso-admin": dict(no_dex, AdminEnabled=True),
            "dex-no-orgs": dict(app, **{"dex-config": {"connectors": [{"type": "github", "id": "github", "name": "GitHub", "config": {"clientID": "x"}}]}}),
            "unpinned": {k: v for k, v in app.items() if k not in ("ArgoCDManifestURL", "ArgoCDManifestSHA256")} | {"argocd-version": "v3.5.7"},
        }
        args = copy.deepcopy(cls.args)
        args["kubernetes"]["projects"] = [{"name": n, "components": [{"name": COMPONENT, "parameters": p}]} for n, p in cls.cases.items()]
        cls.out = cls.generate("cases", args)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def run_command(cls, command, success=True, cwd=None, env=None):
        p = subprocess.run(command, env=env or cls.env, cwd=cwd, text=True, capture_output=True, timeout=120)
        if success and p.returncode:
            raise AssertionError(f"{command[0:2]} failed ({p.returncode}): {p.stdout[-2000:]} {p.stderr[-2000:]}")
        return p

    @classmethod
    def generate(cls, name, args, modules=("kubernetes",)):
        # Each args file gets its own directory: blcli init auto-loads the .env that init-args wrote next to
        # args.yaml, and its overrides (e.g. BLCLI_ARGOCD_GIT_REPOSITORY_URL) would apply to every case.
        (cls.work / "args" / name).mkdir(parents=True)
        f = cls.work / "args" / name / "args.yaml"
        f.write_text(yaml.safe_dump(args, sort_keys=False))
        output = cls.work / name
        command = [cls.blcli, "init", str(ROOT), "--no-resume", "--args", str(f), "--output", str(output)]
        for m in modules:
            command += ["--modules", m]
        cls.run_command(command)
        return output

    def component(self, case):
        return self.out / "kubernetes" / case / COMPONENT

    def install(self, case, **extra_env):
        path = self.component(case)
        log = self.work / f"{case}.log"
        log.write_text("")
        env = dict(self.env, FAKE_LOG=str(log), **extra_env)
        p = subprocess.run(["bash", "./install"], cwd=path, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        return p, log.read_text().splitlines()

    @staticmethod
    def docs(path):
        return [d for d in yaml.safe_load_all(path.read_text()) if d]

    def assert_no_mutation(self, calls):
        for call in calls:
            words = call.split()
            if "--dry-run=client" in words or "--local" in words:
                continue
            self.assertFalse(set(words) & {"apply", "patch", "delete", "create", "replace", "edit"}, f"mutating call: {call}")

    # Rendering

    def test_default_render_is_simple(self):
        # Single environment: local admin, no SSO, SSH deploy key, and the default project still locked down.
        for project in self.args["kubernetes"]["projects"]:
            path = self.defaults / "kubernetes" / project["name"] / COMPONENT
            for script in ["install", "gen_ssh_sealed_secrets.sh"]:
                self.run_command(["bash", "-n", str(path / script)])
            cm = self.docs(path / "argocd-cm.yaml")[0]["data"]
            self.assertEqual(cm["admin.enabled"], "true")
            self.assertNotIn("dex.config", cm)
            self.assertEqual(self.docs(path / "argocd-rbac-cm.yaml")[0]["data"].get("policy.default", ""), "")
            kustomization = self.docs(path / "kustomization.yaml")[0]
            self.assertIn("github-ssh-sealed-secret.yaml", kustomization["resources"])
            self.assertNotIn("github-app-sealed-secret.yaml", kustomization["resources"])
            projects = {d["metadata"]["name"]: d["spec"] for d in self.docs(path / "appproject.yaml")}
            self.assertEqual(projects["default"]["sourceRepos"], [])
            self.assertEqual(projects["apps"]["clusterResourceWhitelist"], [])
            self.assertTrue(all(r.startswith("git@") for r in projects["apps"]["sourceRepos"]))

    def test_default_install_passes_guards(self):
        path = self.defaults / "kubernetes" / self.args["kubernetes"]["projects"][0]["name"] / COMPONENT
        log = self.work / "default-install.log"
        log.write_text("")
        p = subprocess.run(["bash", "./install"], cwd=path, env=dict(self.env, FAKE_LOG=str(log)),
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        out = p.stdout + p.stderr
        for guard in ["no Dex connector is configured", "has no orgs", "GitHubAppID", "is an https URL", "GitAuthMethod must be"]:
            self.assertNotIn(guard, out)

    def test_enterprise_render_is_valid(self):
        for path in [self.component("enterprise")]:
            for script in ["install", "gen_ssh_sealed_secrets.sh", "gen_github_app_sealed_secret.sh", "gen_dex_sealed_secret.sh"]:
                self.run_command(["bash", "-n", str(path / script)])
            cm = self.docs(path / "argocd-cm.yaml")[0]["data"]
            self.assertNotIn("repositories", cm)
            self.assertEqual(cm["admin.enabled"], "false")
            self.assertIn("orgs:", cm["dex.config"])
            self.assertNotIn("clientSecret: X", cm["dex.config"])
            self.assertEqual(self.docs(path / "argocd-rbac-cm.yaml")[0]["data"].get("policy.default", ""), "")
            kustomization = self.docs(path / "kustomization.yaml")[0]
            self.assertIn("github-app-sealed-secret.yaml", kustomization["resources"])
            self.assertIn("argocd-install.yaml", kustomization["resources"])
            projects = {d["metadata"]["name"]: d["spec"] for d in self.docs(path / "appproject.yaml")}
            self.assertEqual(projects["default"]["sourceRepos"], [])
            self.assertEqual(projects["default"]["destinations"], [])
            self.assertEqual(projects["apps"]["clusterResourceWhitelist"], [])
            self.assertTrue(all(r.startswith("https://") for r in projects["apps"]["sourceRepos"]))

    def test_gitops_applications_fit_the_appproject(self):
        apps = list((self.defaults / "gitops").rglob("app.yaml"))
        self.assertTrue(apps)
        for app_file in apps:
            env = app_file.relative_to(self.defaults / "gitops").parts[0]
            component = self.defaults / "kubernetes" / env / COMPONENT
            if not component.exists():
                continue
            projects = {d["metadata"]["name"]: d["spec"] for d in self.docs(component / "appproject.yaml")}
            for app in self.docs(app_file):
                if app.get("kind") != "Application":
                    continue
                spec = app["spec"]
                self.assertIn(spec["project"], projects, f"{app_file}: unknown project")
                project = projects[spec["project"]]
                self.assertIn(spec["source"]["repoURL"], project["sourceRepos"], f"{app_file}: repoURL not allowed by the AppProject")
                self.assertIn(spec["destination"]["namespace"], [d["namespace"] for d in project["destinations"]], f"{app_file}: destination not allowed")

    def test_restrict_default_project_can_be_turned_off(self):
        default = next(d for d in self.docs(self.component("permissive") / "appproject.yaml") if d["metadata"]["name"] == "default")
        self.assertEqual(default["spec"]["sourceRepos"], ["*"])
        self.assertEqual(default["spec"]["destinations"], [{"server": "*", "namespace": "*"}])
        self.assertEqual(default["spec"]["clusterResourceWhitelist"], [{"group": "*", "kind": "*"}])

    def test_ssh_mode_uses_ssh_secret(self):
        kustomization = self.docs(self.component("ssh") / "kustomization.yaml")[0]
        self.assertIn("github-ssh-sealed-secret.yaml", kustomization["resources"])
        self.assertNotIn("github-app-sealed-secret.yaml", kustomization["resources"])

    # Install guards: each must stop before anything is applied.

    def test_install_guards(self):
        cases = {
            "enterprise": (None, "set GitHubAppID and GitHubAppInstallationID"),
            "app-ssh-url": (None, "not an https URL"),
            "ssh-https-url": (None, "is an https URL"),
            "no-sso": (None, "no Dex connector is configured"),
            "dex-no-orgs": (None, "has no orgs"),
            "unpinned": (None, "No sha256 is pinned"),
        }
        for case, (path, message) in cases.items():
            with self.subTest(case=case):
                path = path or self.component(case)
                log = self.work / f"guard-{case}.log"
                log.write_text("")
                p = subprocess.run(["bash", "./install"], cwd=path, env=dict(self.env, FAKE_LOG=str(log)),
                                   stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn(message, p.stdout + p.stderr)
                self.assert_no_mutation(log.read_text().splitlines())

    def test_admin_enabled_without_sso_passes_guard(self):
        p, _ = self.install("no-sso-admin")
        self.assertNotIn("no Dex connector is configured", p.stdout)

    # Install happy path (GitHub App)

    @unittest.skipUnless(shutil.which("kustomize"), "kustomize is required")
    def test_install_github_app_keeps_manifest_and_cleans_up(self):
        self.keys.mkdir(exist_ok=True)
        (self.keys / "argocd_github_app.pem").write_text("fake-app-key\n")
        path = self.component("app")
        p, calls = self.install("app", FAKE_CM_REPOSITORIES="- url: git@github.com:example-org/old.git")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        sealed = (path / "github-app-sealed-secret.yaml").read_text()
        for expected in ["argocd.argoproj.io/secret-type=repo-creds", "--from-literal=url=https://github.com/example-org",
                         "--from-literal=githubAppID=1", "--from-literal=githubAppInstallationID=2", "githubAppPrivateKey="]:
            self.assertIn(expected, sealed)
        self.assertTrue(any("patch configmap argocd-cm" in c and "/data/repositories" in c for c in calls))
        self.assertTrue(any(c.startswith("apply") for c in calls))
        # The verified manifest stays, so kubectl delete -k (blcli destroy) and kustomize build work.
        self.assertEqual((path / "argocd-install.yaml").read_text(), FAKE_MANIFEST)
        self.run_command([self.kustomize, "build", str(path)])
        # A second run reuses it; a tampered copy is replaced by a verified download.
        _, calls = self.install("app")
        self.assertFalse(any(c.startswith("curl") for c in calls))
        (path / "argocd-install.yaml").write_text("tampered\n")
        p, calls = self.install("app")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(any(c.startswith("curl") for c in calls))
        self.assertEqual((path / "argocd-install.yaml").read_text(), FAKE_MANIFEST)

    def test_install_refuses_manifest_with_wrong_digest(self):
        bad = self.work / "bad-manifest.yaml"
        bad.write_text("not the pinned manifest\n")
        path = self.component("permissive")
        p, calls = self.install("permissive", FAKE_MANIFEST_SOURCE=str(bad))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("sha256 mismatch", p.stdout + p.stderr)
        self.assertFalse((path / "argocd-install.yaml").exists())
        self.assert_no_mutation(calls)

    # SSH mode: one key per repository

    @unittest.skipUnless(shutil.which("kustomize"), "kustomize is required")
    def test_install_ssh_mode(self):
        keys = self.work / "ssh-install-keys"
        keys.mkdir()
        (keys / "key_gitops").write_text("k1\n")
        (keys / "key_charts").write_text("k2\n")
        path = self.component("ssh")
        p, calls = self.install("ssh", ARGOCD_KEYS_DIR=str(keys))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        sealed = (path / "github-ssh-sealed-secret.yaml").read_text()
        self.assertIn("argocd.argoproj.io/secret-type=repository", sealed)
        self.assertEqual(sealed.count("kind: Secret"), 2)
        # Placeholders for the missing Dex secret keep the build working.
        self.assertIn("dex-github-placeholder", (path / "dex-github-sealed-secret.yaml").read_text())
        self.assertTrue(any(c.startswith("apply") for c in calls))
        built = list(yaml.safe_load_all(self.run_command([self.kustomize, "build", str(path)]).stdout))
        # The upstream manifest has no namespaces: everything namespaced must land in argocd,
        # and the Namespace objects keep their own names.
        self.assertEqual(sorted(d["metadata"]["name"] for d in built if d["kind"] == "Namespace"), ["app", "argocd"])
        for d in built:
            if d["kind"] != "Namespace":
                self.assertEqual(d["metadata"].get("namespace"), "argocd", d["metadata"]["name"])

    def test_ssh_seals_each_repository_with_its_own_key(self):
        keys = self.work / "ssh-keys"
        keys.mkdir()
        (keys / "key_gitops").write_text("k1\n")
        (keys / "key_charts").write_text("k2\n")
        path = self.component("ssh")
        log = self.work / "ssh.log"
        log.write_text("")
        env = dict(self.env, FAKE_LOG=str(log), ARGOCD_KEYS_DIR=str(keys))
        self.run_command(["bash", "./gen_ssh_sealed_secrets.sh"], cwd=path, env=env)
        creates = [c for c in log.read_text().splitlines() if c.startswith("create secret")]
        self.assertEqual(len(creates), 2)
        self.assertIn(f"url=git@github.com:example-org/gitops.git", creates[0])
        self.assertIn(f"sshPrivateKey={keys}/key_gitops", creates[0])
        self.assertIn(f"sshPrivateKey={keys}/key_charts", creates[1])
        (keys / "key_charts").unlink()
        p = self.run_command(["bash", "./gen_ssh_sealed_secrets.sh"], cwd=path, env=env, success=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("key_charts", p.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
