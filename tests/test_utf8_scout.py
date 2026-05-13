import unittest
from pathlib import Path
from unittest import mock

import utf8_scout


class TestUtf8Scout(unittest.TestCase):
    def test_scan_utf8_detects_non_utf8_file(self) -> None:
        root = Path("C:/repo")
        ok = root / "ok.txt"
        bad = root / "bad.txt"

        def fake_read_bytes(p: Path) -> bytes:
            if p == ok:
                return b"hello"
            if p == bad:
                return "中文".encode("cp950")
            raise AssertionError(f"unexpected path: {p}")

        with mock.patch.object(utf8_scout, "_iter_files", return_value=[ok, bad]):
            with mock.patch.object(Path, "read_bytes", autospec=True, side_effect=fake_read_bytes):
                results = utf8_scout.scan_utf8(
                    root,
                    include=["**/*.txt"],
                    exclude=[],
                    exclude_dirs=set(),
                )

        by_name = {r.path.name: r for r in results}
        self.assertTrue(by_name["ok.txt"].ok_utf8)
        self.assertFalse(by_name["bad.txt"].ok_utf8)

    def test_try_convert_to_utf8_writes_backup_and_converts(self) -> None:
        p = Path("C:/repo/bad.txt")
        raw = "中文".encode("cp950")
        backup = Path("C:/repo/bad.txt.bak")

        def fake_exists(path: Path) -> bool:
            # Pretend the backup does not exist yet.
            return path != backup

        with (
            mock.patch.object(Path, "read_bytes", autospec=True, return_value=raw),
            mock.patch.object(Path, "exists", autospec=True, side_effect=fake_exists),
            mock.patch.object(Path, "write_bytes", autospec=True) as write_bytes,
            mock.patch.object(Path, "write_text", autospec=True) as write_text,
        ):
            ok, msg = utf8_scout.try_convert_to_utf8(p, from_encodings=["cp950"], make_backup=True)

        self.assertTrue(ok, msg)
        write_bytes.assert_called_once()
        self.assertEqual(write_bytes.call_args.args[0], backup)
        self.assertEqual(write_bytes.call_args.args[1], raw)

        write_text.assert_called_once()
        self.assertEqual(write_text.call_args.args[0], p)
        self.assertEqual(write_text.call_args.kwargs["encoding"], "utf-8")
