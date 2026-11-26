"""Persistence and pricing regressions; the HTTP surface is documented in README."""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "tenant_api.py"


def load_module(base: str):
    os.environ["TENANT_BASE"] = base
    os.environ["TENANT_TENANTS_DIR"] = os.path.join(base, "tenants")
    spec = importlib.util.spec_from_file_location("tenant_api_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class State(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.base = self.td.name
        self.m = load_module(self.base)

    def tearDown(self):
        self.td.cleanup()

    def test_migrate_adds_a_key_once(self):
        self.m.save({"acme": {}})
        self.m.migrate()
        first = self.m.load()["acme"]["api_key"]
        self.assertTrue(first)
        self.m.migrate()
        self.assertEqual(self.m.load()["acme"]["api_key"], first)

    def test_bump_counts_per_endpoint(self):
        self.m.save({"acme": {}})
        self.m.bump("acme", "verify")
        self.m.bump("acme", "verify")
        self.m.bump("acme", "sandbox")
        usage = self.m.load()["acme"]["usage"]
        self.assertEqual(usage, {"verify": 2, "sandbox": 1})

    def test_bump_unknown_tenant_is_a_noop(self):
        self.m.save({})
        self.m.bump("nobody", "verify")
        self.assertEqual(self.m.load(), {})

    def test_billing_uses_the_documented_prices(self):
        self.assertEqual(self.m.PRICES["sandbox"], 0.02)
        self.assertEqual(self.m.PRICES["verify"], 0.005)

    def test_defaults_are_loopback(self):
        self.assertEqual(self.m.HOST, "127.0.0.1")
        self.assertEqual(self.m.FC_HOST, "127.0.0.1")
        self.assertFalse(self.m.ALLOW_PRIVATE)


class Safety(unittest.TestCase):
    def test_tenant_names_cannot_escape_the_directory(self):
        with tempfile.TemporaryDirectory() as td:
            m = load_module(td)
            self.assertTrue(m.safe_name("acme-1"))
            for bad in ("../etc", "a/b", "..", "A B"):
                self.assertFalse(m.safe_name(bad), bad)

    def test_a_truncated_audit_trail_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            m = load_module(td)
            directory = m._ai_dir("acme")
            m.ai_act_log("acme", "ops", "event", summary="one")
            m.ai_act_log("acme", "ops", "event", summary="two")
            path = os.path.join(directory, "audit_trail.jsonl")
            lines = open(path).read().splitlines()
            open(path, "w").write(lines[0] + "\n")       # delete the tail
            result = m.ai_act_verify("acme")
            self.assertFalse(result["ok"])
            self.assertEqual(result["code"], "truncated")

    def test_an_empty_api_key_does_not_match(self):
        with tempfile.TemporaryDirectory() as td:
            m = load_module(td)
            m.save({"acme": {"api_key": ""}})
            self.assertFalse(bool(m.load()["acme"]["api_key"]))


class RateLimit(unittest.TestCase):
    def test_the_bucket_refuses_after_the_limit(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["TENANT_RATE_PER_MIN"] = "2"
            try:
                m = load_module(td)
            finally:
                os.environ.pop("TENANT_RATE_PER_MIN", None)
            self.assertTrue(m.rate_ok("1.2.3.4", now=1000))
            self.assertTrue(m.rate_ok("1.2.3.4", now=1000))
            self.assertFalse(m.rate_ok("1.2.3.4", now=1000))
            self.assertTrue(m.rate_ok("1.2.3.4", now=1061))
            self.assertTrue(m.rate_ok("5.6.7.8", now=1061))


class StateFile(unittest.TestCase):
    def test_tenants_file_is_json_and_readable(self):
        with tempfile.TemporaryDirectory() as td:
            m = load_module(td)
            m.save({"x": {"api_key": "k"}})
            data = json.loads(open(os.path.join(td, "tenants.json")).read())
            self.assertEqual(data["x"]["api_key"], "k")


if __name__ == "__main__":
    unittest.main()
