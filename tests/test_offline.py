"""Offline checks for export and MCP hardening. No network and no real cookies."""

import base64
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXP = load("grok_export_under_test", "grok-bot-export.py")
MCP = load("grok_mcp_under_test", "grok-bot-mcp.py")


class ExportHelpers(unittest.TestCase):
    def test_sanitize_blocks_path_pieces(self):
        name = EXP.sanitize("../../etc/passwd")
        self.assertNotIn("/", name)
        self.assertNotIn("\\", name)
        self.assertEqual(EXP.sanitize(".."), "bot")
        self.assertEqual(EXP.sanitize("a\x00b"), "a_b")
        parent = Path(tempfile.mkdtemp())
        target = parent / name
        self.assertEqual(target.resolve().parent, parent.resolve())

    def test_cookie_header_drops_controls_and_empty(self):
        header = EXP.cookie_header({
            "sso": "alpha",
            "sso-rw": "beta",
            "bad": "one\r\nSet-Cookie: x",
            "empty": "",
            "none": None,
        })
        self.assertEqual(header, "sso=alpha; sso-rw=beta")
        self.assertNotIn("Set-Cookie", header)

    def test_path_segment_encodes_slash(self):
        self.assertEqual(EXP.path_segment("conv-1"), "conv-1")
        encoded = EXP.path_segment("a/../../x")
        self.assertNotIn("/", encoded)
        self.assertIsNone(EXP.path_segment("bad\nid"))

    def test_redirect_stays_on_grok(self):
        req = urllib.request.Request("https://grok.com/rest/app-chat/conversations")
        handler = EXP._SameHostRedirect()
        allowed = handler.redirect_request(
            req, None, 302, "Found", {}, "https://grok.com/rest/app-chat/next")
        self.assertIsNotNone(allowed)
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(
                req, None, 302, "Found", {}, "https://evil.example/collect")

    def test_redact_hides_cookie_assignment(self):
        secret = "sso-example-not-a-real-token"
        text = EXP.redact("Cookie: " + secret)
        self.assertNotIn(secret, text)
        self.assertIn("[redacted]", text)

    def test_normalize_survives_bad_bodies(self):
        none_body = EXP.normalize_entry({"entryKind": "message", "seq": "nope"}, None)
        self.assertEqual(none_body["seq"], 0)
        self.assertEqual(none_body["type"], "message")
        listed = EXP.normalize_entry({"entryKind": "message", "seq": 3}, ["not", "a", "dict"])
        self.assertEqual(listed["seq"], 3)
        self.assertNotIn("role", listed)
        braced = EXP.AGENTS_MD.replace("{count}", "1").replace("{bots}", "{oops}")
        self.assertIn("{oops}", braced)

    def test_pkcs7_rejects_bad_padding(self):
        self.assertIsNone(EXP._pkcs7_unpad(b""))
        self.assertIsNone(EXP._pkcs7_unpad(b"abc\x04"))
        self.assertEqual(EXP._pkcs7_unpad(b"abcd" + bytes([4]) * 4), b"abcd")

    def test_restrict_tree_modes_and_skips_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "export"
            root.mkdir()
            nested = root / "bot"
            nested.mkdir()
            target = Path(tmp) / "secret.txt"
            target.write_text("keep", encoding="utf-8")
            os.chmod(target, 0o644)
            link = nested / "leak"
            link.symlink_to(target)
            note = nested / "meta.json"
            note.write_text("{}", encoding="utf-8")
            os.chmod(note, 0o644)
            EXP.restrict_tree(str(root))
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(note.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")

    def test_download_keeps_only_complete_files(self):
        class Client:
            def __init__(self, chunks):
                self.chunks = chunks

            def read_attachment_chunk(self, _agent, _path, offset, length):
                if offset == 0 and length == 1:
                    return {"totalSize": 4}
                return {"bytesBase64": self.chunks}

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "pic.bin")
            ok = EXP.download_attachment(Client(base64.b64encode(b"abcd").decode()), "a", "remote", dest)
            self.assertTrue(ok)
            self.assertEqual(Path(dest).read_bytes(), b"abcd")
            self.assertFalse(os.path.exists(dest + ".partial"))
            self.assertEqual(stat.S_IMODE(os.stat(dest).st_mode), 0o600)

            missing = os.path.join(tmp, "missing.bin")
            self.assertFalse(EXP.download_attachment(Client(""), "a", "remote", missing))
            self.assertFalse(os.path.exists(missing))
            self.assertFalse(os.path.exists(missing + ".partial"))

    def test_workers_rejected_before_cookie_read(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "grok-bot-export.py"), "--workers", "0"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("1 and 32", proc.stderr)


class McpGuards(unittest.TestCase):
    def test_symlink_outside_export_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "export"
            inside = root / "01_example"
            inside.mkdir(parents=True)
            (inside / "meta.json").write_text(json.dumps({"name": "Example Bot", "agentId": "bot_example"}), encoding="utf-8")
            (inside / "messages.jsonl").write_text(
                json.dumps({"type": "message", "role": "user", "content": "hello example"}) + "\n",
                encoding="utf-8",
            )
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (outside / "meta.json").write_text(json.dumps({"name": "Outside"}), encoding="utf-8")
            (outside / "messages.jsonl").write_text(
                json.dumps({"type": "message", "role": "user", "content": "outside-secret-marker"}) + "\n",
                encoding="utf-8",
            )
            (root / "linked").symlink_to(outside)
            MCP.DATA_DIR = str(root)
            names = [os.path.basename(p) for p in MCP.find_bot_folders()]
            self.assertEqual(names, ["01_example"])
            self.assertEqual(MCP.load_messages("linked"), [])
            listed = MCP.tool_list_bots()
            self.assertIn("Example Bot", listed)
            self.assertNotIn("outside-secret-marker", listed)
            missed = MCP.tool_search("outside-secret-marker")
            self.assertTrue(missed.startswith("未找到"))
            capped = MCP.tool_get_bot("Example Bot", limit=-3)
            self.assertIn("Example Bot", capped)
            self.assertNotIn("hello example", capped)
            self.assertIn("hello example", MCP.tool_get_bot("Example Bot", limit=5))
            self.assertIn("未找到", MCP.tool_get_bot("../linked"))

    def test_unknown_method_and_argument_clamps(self):
        reply = MCP.handle_request({"jsonrpc": "2.0", "id": 7, "method": "nope", "params": {}})
        self.assertEqual(reply["error"]["code"], -32601)
        self.assertEqual(MCP.clamp_int(-5, 200, 0, 10000), 0)
        self.assertEqual(MCP.clamp_int("bad", 2, 0, 10), 2)


if __name__ == "__main__":
    unittest.main()
