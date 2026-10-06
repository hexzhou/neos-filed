"""验证真实转换、资源删除和转换失败时保留已发布资源。"""

import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

spec = importlib.util.spec_from_file_location(
    "sync_field_artwork", Path(__file__).resolve().parents[1] / "scripts/sync-field-artwork.py",
)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def write_png(path):
    def chunk(kind, data):
        return (
            struct.pack("!I", len(data)) + kind + data
            + struct.pack("!I", zlib.crc32(kind + data))
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b""),
    )


@unittest.skipUnless(shutil.which("cwebp"), "需要安装 cwebp")
class SynchronizeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source"
        self.output = root / "published"
        self.source.mkdir()

    def test_converts_images_and_removes_deleted_artwork(self):
        write_png(self.source / "00123.png")
        write_png(self.source / "456.PNG")
        (self.source / "notes.txt").write_text("ignored")
        sync.synchronize(self.source, "revision-1", self.output)
        self.assertEqual(json.loads((self.output / "manifest.json").read_text()), [123, 456])
        self.assertEqual(json.loads((self.output / "source.json").read_text())["revision"], "revision-1")
        image = (self.output / "123.webp").read_bytes()
        self.assertEqual(image[:4], b"RIFF")
        self.assertEqual(image[8:12], b"WEBP")
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        sync.synchronize(self.source, "revision-1", self.output)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})
        (self.source / "456.PNG").unlink()
        sync.synchronize(self.source, "revision-2", self.output)
        self.assertFalse((self.output / "456.webp").exists())
        self.assertEqual(json.loads((self.output / "manifest.json").read_text()), [123])

    def test_failed_conversion_preserves_published_images_and_manifest(self):
        write_png(self.source / "123.png")
        sync.synchronize(self.source, "revision-1", self.output)
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        (self.source / "456.png").write_bytes(b"invalid PNG")
        with self.assertRaises(subprocess.CalledProcessError):
            sync.synchronize(self.source, "revision-2", self.output)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_empty_or_ambiguous_source_preserves_published_resources(self):
        write_png(self.source / "123.png")
        sync.synchronize(self.source, "revision-1", self.output)
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        write_png(self.source / "00123.png")
        with self.assertRaises(ValueError):
            sync.synchronize(self.source, "revision-2", self.output)
        (self.source / "00123.png").unlink()
        (self.source / "123.png").unlink()
        with self.assertRaises(ValueError):
            sync.synchronize(self.source, "revision-2", self.output)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})


if __name__ == "__main__":
    unittest.main()
