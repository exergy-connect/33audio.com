import base64
import gzip
import json
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

from academy import CONTENT, DATA, ROOT
from academy.build import BuildError, Builder, front_matter
from academy.charts import DatasetError, validate_dataset
from academy.markdown import render

SITE = json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))
PROPOSALS = ROOT / "network" / "labnet" / "proposals"


def build(real_dir: Path | None = None) -> tuple[Path, dict, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    out = Path(tmp.name) / "dist"
    empty = Path(tmp.name) / "no-real"
    empty.mkdir()
    info = Builder(out, real_dir or empty).run()
    return out, info, tmp


class AcademyBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.info, cls.tmp = build()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, path: str) -> str:
        return (self.out / path / "index.html").read_text(encoding="utf-8")

    def test_information_architecture(self):
        for path in ("", "paths/", "courses/", "labs/", "explore/", "reference/", "reference/adr/", "reference/labnet/", "reference/real-vs-simulated/"):
            self.assertTrue((self.out / path / "index.html").is_file(), path)
        for topic in SITE["topics"]:
            self.assertIn("Explore", self.page(f"explore/{topic['slug']}/"))
            self.assertIn("Lab", self.page(f"labs/{topic['slug']}/"))
        for p in SITE["paths"]:
            self.assertTrue((self.out / "paths" / p["slug"] / "index.html").is_file())

    def test_every_chart_and_labnet_figure_has_a_badge(self):
        figures = 0
        for html_file in self.out.rglob("*.html"):
            text = html_file.read_text(encoding="utf-8")
            for fig in re.findall(r'<figure class="(?:chart|labnet)-figure".*?</figcaption>', text, flags=re.S):
                figures += 1
                self.assertRegex(fig, r"badge-(real|sim)")
        self.assertGreater(figures, 5)

    def test_without_real_data_everything_is_simulated(self):
        self.assertTrue(all(d["kind"] == "simulated" for d in self.info["datasets"].values()))
        self.assertNotIn("REAL TELEMETRY</span><span class=\"badge-meta\">", self.page("explore/observability/"))

    def test_delivery_uses_labnet_runs(self):
        html = self.page("explore/delivery/")
        self.assertIn('data-labnet="anycast-edge"', html)
        self.assertIn('data-labnet="anycast-edge-failover"', html)
        self.assertIn("Computed by lab.net @ 06c7162", html)
        self.assertIn("lk on-path", html)
        self.assertIn("https://github.com/exergy-connect/lab.net/blob/06c71623b044e5ee2d4a9bcfe052bc1b9fe7c6d2/src/lab/validation/run.js", html)
        self.assertNotIn("labnet-trace", html)
        self.assertTrue((self.out / "labnet" / "anycast-edge.pcapng").is_file())

    def test_open_in_labnet_link_carries_the_topology(self):
        html = self.page("explore/delivery/")
        link = re.search(r'href="https://exergy-connect.com/lab.net/#lab=([^"]+)"', html).group(1)
        padded = unquote(link) + "=" * (-len(link) % 4)
        source = gzip.decompress(base64.urlsafe_b64decode(padded))
        self.assertEqual(source, (ROOT / "network/labnet/anycast-edge.xp").read_bytes())

    def test_pending_extensions_link_their_proposals(self):
        html = self.page("reference/labnet/")
        index = json.loads((PROPOSALS / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(html.count("Pending lab.net extension"), len(index["proposals"]))
        for proposal in index["proposals"]:
            self.assertTrue(proposal.get("issue_url"), proposal["slug"])
            self.assertIn(proposal["issue_url"], html)
        self.assertIn("Pending lab.net extension", self.page("explore/security/"))

    def test_real_dataset_gets_real_badge(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp)
            data = json.loads((DATA / "simulated" / "local-latency.json").read_text(encoding="utf-8"))
            data.update(kind="real", source="unit test", collected_at="2026-11-16T00:00:00Z")
            data.pop("make_real")
            (real / "local-latency.json").write_text(json.dumps(data), encoding="utf-8")
            out, info, holder = build(real)
            try:
                self.assertEqual(info["datasets"]["local-latency"]["kind"], "real")
                self.assertIn("REAL TELEMETRY", (out / "explore/observability/index.html").read_text(encoding="utf-8"))
            finally:
                holder.cleanup()

    def test_embeds_are_repo_files_at_the_build_commit(self):
        html = self.page("explore/deploy/")
        self.assertIn(f"/blob/{self.info['sha']}/functions/api/stock.js", html)
        self.assertGreater(len(self.info["embeds"]), 30)


class DatasetPolicyTests(unittest.TestCase):
    def test_policy(self):
        validate_dataset("ok", {"kind": "simulated", "make_real": ["x"]})
        validate_dataset("ok", {"kind": "real", "source": "s", "collected_at": "t"})
        for bad in ({"kind": "real", "source": "s"}, {"kind": "simulated"}, {"kind": "measured"}, {}):
            with self.assertRaises(DatasetError):
                validate_dataset("bad", bad)

    def test_missing_embed_fails_the_build(self):
        builder = Builder(Path(tempfile.mkdtemp()) / "dist")
        with self.assertRaises(BuildError):
            builder.embed('worker/cart.js "function doesNotExist"')
        with self.assertRaises(BuildError):
            builder.embed("no/such/file.js")


class MarkdownTests(unittest.TestCase):
    def test_render(self):
        toc = []
        html = render("## Title\n\nSome `code` and **bold** [link](/x/).\n\n- a\n- b\n\n```output\nok\n```", lambda n, a: "", lambda h: h, toc)
        self.assertIn('<h2 id="title">', html)
        self.assertIn("<code>code</code>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("Expected output", html)
        self.assertEqual(toc, [(2, "title", "Title")])

    def test_front_matter(self):
        meta, body = front_matter("---\ntitle: T\n---\nbody\n")
        self.assertEqual(meta, {"title": "T"})
        self.assertEqual(body, "body\n")


class LabnetIntegrationTests(unittest.TestCase):
    def test_committed_runs_pass_and_name_the_pinned_commit(self):
        workflow = (ROOT / ".github/workflows/academy.yml").read_text(encoding="utf-8")
        pinned = re.search(r"LABNET_COMMIT: ([0-9a-f]{40})", workflow).group(1)
        runs = sorted((DATA / "labnet").glob("*.json"))
        self.assertEqual(sorted(p.stem for p in runs), ["anycast-edge", "anycast-edge-failover"])
        for path in runs:
            run = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(run["kind"], "simulated")
            self.assertEqual(run["simulator"]["commit"], pinned)
            self.assertTrue(all(r["ok"] for r in run["results"]), path.name)
            self.assertTrue((ROOT / run["topology_file"]).is_file())
            self.assertTrue(any(r.get("hops") for r in run["results"]))

    def test_failover_moves_to_dfw(self):
        normal = json.loads((DATA / "labnet/anycast-edge.json").read_text(encoding="utf-8"))
        failover = json.loads((DATA / "labnet/anycast-edge-failover.json").read_text(encoding="utf-8"))
        route = lambda run: next(r for r in run["tables"]["isp_hou"]["locRib"] if r["prefix"] == "192.0.2.0/24")
        self.assertEqual(route(normal)["aspath"], "13335")
        self.assertEqual(route(failover)["aspath"], "64520 13335")

    def test_proposals_are_complete(self):
        index = json.loads((PROPOSALS / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(index["proposals"]), 7)
        for proposal in index["proposals"]:
            text = (PROPOSALS / f"{proposal['slug']}.md").read_text(encoding="utf-8")
            for heading in ("## Motivation", "## Minimal proposed design", "## Example", "## Out of scope", "## How the Academy will use it"):
                self.assertIn(heading, text, proposal["slug"])


if __name__ == "__main__":
    unittest.main()
