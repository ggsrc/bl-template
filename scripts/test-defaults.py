#!/usr/bin/env python3
"""Render the single-environment defaults and examples/multi-env offline, and check what each layout installs.

Generated files stay in workspace/. Needs blcli on PATH; no network, kubectl or cloud access.
"""
import copy
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "multi-env"


class Layouts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.chdir(ROOT)
        Path("workspace").mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix="defaults-", dir="workspace")
        cls.work = Path(cls.temp.name).resolve()
        tools = cls.work / "bin"
        tools.mkdir()
        # Do not let blcli install tools or call a real kubectl/terraform.
        for tool in ["kubectl", "terraform", "istioctl", "helm"]:
            p = tools / tool
            p.write_text("#!/bin/sh\nexit 97\n")
            p.chmod(0o755)
        cls.blcli = shutil.which("blcli")
        if not cls.blcli:
            raise RuntimeError("install blcli before running these tests")
        cls.env = {
            "PATH": str(tools) + os.pathsep + os.environ["PATH"],
            "HOME": str(cls.work / "home"),
            "BLCLI_KEYS_DIR": str(cls.work / "keys"),
        }
        Path(cls.env["HOME"]).mkdir()

        cls.run_command([cls.blcli, "init-args", str(ROOT), "-o", str(cls.work / "args.yaml")])
        defaults = yaml.safe_load((cls.work / "args.yaml").read_text())
        multi = copy.deepcopy(defaults)
        for module in ["terraform", "kubernetes", "gitops"]:
            section = yaml.safe_load((EXAMPLE / f"{module}.default.yaml").read_text())
            section.pop("version", None)
            multi[module] = section
        cls.single = cls.generate("single", defaults)
        cls.multi = cls.generate("multi", multi)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def run_command(cls, command):
        p = subprocess.run(command, env=cls.env, text=True, capture_output=True, timeout=120)
        if p.returncode:
            raise AssertionError(f"{command[0:2]} failed ({p.returncode}): {p.stdout[-2000:]} {p.stderr[-2000:]}")
        return p

    @classmethod
    def generate(cls, name, args):
        f = cls.work / f"{name}-args.yaml"
        f.write_text(yaml.safe_dump(args, sort_keys=False))
        cls.run_command([cls.blcli, "check", "args", "--args", str(f), "-r", str(ROOT)])
        output = cls.work / name
        cls.run_command([cls.blcli, "init", str(ROOT), "--no-resume", "--args", str(f), "--output", str(output)])
        return output

    @staticmethod
    def components(output, project):
        return sorted(p.name for p in (output / "kubernetes" / project).iterdir())

    @staticmethod
    def values(path):
        return yaml.safe_load(path.read_text())

    # Single environment (template defaults)

    def test_single_env_renders_only_prd(self):
        for module in ["kubernetes", "gitops"]:
            self.assertEqual(sorted(p.name for p in (self.single / module).iterdir() if p.is_dir()), ["prd"])
        self.assertEqual(sorted(p.name for p in (self.single / "terraform" / "gcp").iterdir() if p.name != "modules"), ["prd"])

    def test_single_env_has_no_istio(self):
        # victoria-metrics-operator used to depend on istio, and blcli pulls dependencies in transitively.
        self.assertFalse(any("istio" in c for c in self.components(self.single, "prd")))
        for vs in (self.single / "gitops").rglob("virtualservice.yaml"):
            self.assertEqual(vs.read_text().strip(), "", vs)

    def test_single_env_monitoring_is_self_contained(self):
        stack = self.values(self.single / "kubernetes/prd/3-victoria-metrics-operator/values-override.yaml")["victoria-metrics-k8s-stack"]
        self.assertTrue(stack["vmsingle"]["enabled"])
        self.assertTrue(stack["vmalert"]["enabled"])
        self.assertTrue(stack["alertmanager"]["enabled"])
        self.assertNotIn("remoteWrite", stack["vmagent"]["spec"])

    def test_single_env_grafana_needs_no_google(self):
        path = self.single / "kubernetes/prd/4-grafana/values-corp.yaml"
        values = self.values(path)
        self.assertFalse(values["googleAuth"]["enabled"])
        ini = values["grafana"]["grafana.ini"]
        self.assertFalse(ini["auth"]["disable_login_form"])
        self.assertNotIn("auth.google", ini)
        self.assertNotIn("envFromSecrets", values["grafana"])
        names = [d["name"] for d in values["grafana"]["datasources"]["datasources.yaml"]["datasources"]]
        self.assertNotIn("loki-logs", names)
        self.assertIn(":8429", values["grafana"]["datasources"]["datasources.yaml"]["datasources"][0]["url"])

    # examples/multi-env keeps the previous behaviour

    def test_multi_env_renders_three_environments(self):
        self.assertEqual(sorted(p.name for p in (self.multi / "kubernetes").iterdir() if p.is_dir()), ["corp", "prd", "stg"])
        for project in ["corp", "prd", "stg"]:
            self.assertIn("1-istio", self.components(self.multi, project))

    def test_multi_env_ships_metrics_to_corp(self):
        for project in ["corp", "prd", "stg"]:
            stack = self.values(self.multi / f"kubernetes/{project}/3-victoria-metrics-operator/values-override.yaml")["victoria-metrics-k8s-stack"]
            self.assertFalse(stack["vmsingle"]["enabled"], project)
            self.assertTrue(stack["vmagent"]["spec"]["remoteWrite"][0]["url"].startswith("http://"), project)

    def test_multi_env_keeps_istio_routing_and_google_sign_in(self):
        vss = list((self.multi / "gitops").rglob("virtualservice.yaml"))
        self.assertTrue(vss)
        for vs in vss:
            self.assertEqual(self.values(vs)["kind"], "VirtualService", vs)
        values = self.values(self.multi / "kubernetes/corp/4-grafana/values-corp.yaml")
        self.assertTrue(values["googleAuth"]["enabled"])
        self.assertTrue(values["grafana"]["grafana.ini"]["auth"]["disable_login_form"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
