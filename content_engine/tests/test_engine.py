"""Run: python -m unittest discover -s content_engine/tests -t ."""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from content_engine.backends.comfy import ComfyBackend, fill_template
from content_engine.models import Brand, Campaign
from content_engine.planner import check_compliance, plan

ROOT = Path(__file__).resolve().parents[1]
BRAND = Brand.load(ROOT / "brands/offline/brand.json")
CAMPAIGN = Campaign.load(ROOT / "brands/offline/campaigns/switch_off_q4.json")
WORKFLOW = ROOT / "workflows/sdxl_txt2img.api.json"
PNG = b"\x89PNG\r\n\x1a\nfake"


class PlannerTest(unittest.TestCase):
    def test_matrix_respects_affinity(self):
        specs = plan(BRAND, CAMPAIGN)
        # busy_professional: 2 products, slow_living: 2, gen_z_detox: all 3 -> 7 x 3 formats
        self.assertEqual(len(specs), 21)
        self.assertFalse(any(s.audience == "busy_professional" and s.product == "hair_oil"
                             for s in specs))
        self.assertEqual(len({s.seed for s in specs}), 21)

    def test_copy_is_clean_and_localized(self):
        for s in plan(BRAND, CAMPAIGN):
            self.assertEqual(s.compliance, [], s.id)
            self.assertEqual(set(s.copy), {"hu", "en"})

    def test_compliance_flags_banned_claims(self):
        self.assertTrue(check_compliance("Megállítja a hajhullást!", BRAND))
        self.assertTrue(check_compliance("100% natural formula", BRAND))
        self.assertEqual(check_compliance("Soft, calm hair.", BRAND), [])

    def test_fill_template_types(self):
        out = fill_template({"w": "{{width}}", "t": "a {{prompt}}"}, {"width": 1080, "prompt": "cat"})
        self.assertEqual(out, {"w": 1080, "t": "a cat"})


class FakeComfy(BaseHTTPRequestHandler):
    """Mimics Comfy Cloud: X-API-Key auth, /api/prompt, /api/history, /api/view -> 302."""
    submitted = []

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.headers.get("X-API-Key") != "comfyui-test":
            return self._send(401, b'{"error":"unauthorized"}')
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeComfy.submitted.append(body)
        self._send(200, json.dumps({"prompt_id": f"p{len(FakeComfy.submitted)}"}).encode())

    def do_GET(self):
        url = urlparse(self.path)
        if url.path.startswith("/signed/"):
            # Signed storage must NOT receive the API key.
            if self.headers.get("X-API-Key"):
                return self._send(400)
            return self._send(200, PNG)
        if self.headers.get("X-API-Key") != "comfyui-test":
            return self._send(401)
        if url.path.startswith("/api/history/"):
            pid = url.path.rsplit("/", 1)[1]
            prefix = FakeComfy.submitted[int(pid[1:]) - 1]["prompt"]["9"]["inputs"]["filename_prefix"]
            hist = {pid: {"status": {"status_str": "success"}, "outputs": {"9": {"images": [
                {"filename": f"{prefix}_00001_.png", "subfolder": "", "type": "output"}]}}}}
            return self._send(200, json.dumps(hist).encode())
        if url.path == "/api/view":
            name = parse_qs(url.query)["filename"][0]
            return self._send(302, headers={"Location": f"http://127.0.0.1:{self.server.server_port}/signed/{name}"})
        self._send(404)


class ComfyBackendTest(unittest.TestCase):
    def test_end_to_end_against_fake_cloud(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeComfy)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            backend = ComfyBackend(WORKFLOW, base_url=f"http://127.0.0.1:{server.server_port}",
                                   api_key="comfyui-test", poll_seconds=0.01)
            spec = plan(BRAND, CAMPAIGN)[0]
            with tempfile.TemporaryDirectory() as d:
                backend.render(spec, Path(d))
                self.assertEqual((Path(d) / spec.assets[0]).read_bytes(), PNG)
            graph = FakeComfy.submitted[-1]["prompt"]
            self.assertEqual(graph["5"]["inputs"]["width"], spec.format.width)
            self.assertEqual(graph["3"]["inputs"]["seed"], spec.seed)
            self.assertIn("Offline", graph["6"]["inputs"]["text"])
            self.assertEqual(spec.backend_job["prompt_id"], "p1")
        finally:
            server.shutdown()

    def test_bad_key_raises(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeComfy)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            backend = ComfyBackend(WORKFLOW, base_url=f"http://127.0.0.1:{server.server_port}",
                                   api_key="wrong")
            with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
                backend.submit(plan(BRAND, CAMPAIGN)[0])
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
