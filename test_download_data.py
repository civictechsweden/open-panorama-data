import csv
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from convert import convert_snapshot
from download_data import download_board, fetch_json, load_published_board


class PublishedBoardTests(unittest.TestCase):
    def setUp(self):
        self.metadata: dict[str, Any] = {
            "id": "version-id",
            "version": "V5.1",
            "updatedAt": "2026-11-06T13:49:20Z",
            "content": {
                "oldBlobUrl": None,
                "modules": [
                    {"type": "INTERVENTIONS", "blobUrl": "https://example.org/actions"},
                    {"type": "CORE", "blobUrl": "https://example.org/core"},
                    {"type": "SEARCH", "blobUrl": "https://example.org/search"},
                ],
            },
        }

    def load_board(self, metadata):
        with (
            patch("download_data.discover_board_id", return_value="board-id"),
            patch(
                "download_data.discover_api_base_url",
                return_value="https://example.org/",
            ),
            patch("download_data.fetch_json", return_value=metadata) as fetch,
        ):
            board = load_published_board("https://example.org/site")
        fetch.assert_called_once_with(
            "https://example.org/published-boards/v2/board-id"
        )
        return board

    def test_load_modular_board_with_null_legacy_url(self):
        board = self.load_board(self.metadata)
        self.assertEqual(board.board_id, "board-id")
        self.assertEqual(board.version_id, "version-id")
        self.assertEqual(board.version, "V5.1")
        self.assertEqual(board.updated_at, self.metadata["updatedAt"])
        self.assertEqual(
            board.module_urls,
            {
                module["type"]: module["blobUrl"]
                for module in self.metadata["content"]["modules"]
            },
        )

    def test_missing_modules_raise_clear_error(self):
        self.metadata["content"]["modules"] = []
        with self.assertRaisesRegex(RuntimeError, "Missing module URLs"):
            self.load_board(self.metadata)

    def test_missing_module_url_raises_clear_error(self):
        self.metadata["content"]["modules"][0]["blobUrl"] = None
        with self.assertRaisesRegex(RuntimeError, "Missing module URLs"):
            self.load_board(self.metadata)

    def test_fetch_json_accepts_bom_and_array_modules(self):
        with patch(
            "download_data.urlopen",
            return_value=BytesIO(b'\xef\xbb\xbf[{"id":"action-id"}]'),
        ):
            self.assertEqual(
                fetch_json("https://example.org/search"), [{"id": "action-id"}]
            )

    def test_download_all_modules_and_export_actions(self):
        board = self.load_board(self.metadata)
        core = {
            "actionTypes": [{"id": "type-id", "displayValue": "Styrmedel"}],
            "actionStatuses": [{"id": "status-id", "displayValue": "Beslutat"}],
            "actionTags": [{"id": "tag-id", "displayValue": "Sverige"}],
        }
        actions = {
            "action-id": {
                "id": "action-id",
                "title": "Åtgärd",
                "actionProperties": {
                    "type": "type-id",
                    "swimlane": "status-id",
                    "actionTags": ["tag-id"],
                    "description": r"\u003cp\u003eÅtgärd \u0026 klimat\u003c/p\u003e",
                },
            },
        }
        modules = {
            "CORE": core,
            "INTERVENTIONS": actions,
            "SEARCH": [{"id": "action-id"}],
        }
        payloads = {
            board.module_urls[name]: json.dumps(data) for name, data in modules.items()
        }
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "data" / "panorama.json"
            with patch(
                "download_data.fetch_text", side_effect=payloads.__getitem__
            ) as fetch:
                download_board(board, destination)
            self.assertCountEqual(
                [call.args[0] for call in fetch.call_args_list],
                board.module_urls.values(),
            )
            snapshot = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(set(snapshot), set(modules))
            self.assertEqual(snapshot["CORE"], core)
            self.assertEqual(snapshot["SEARCH"], modules["SEARCH"])
            self.assertEqual(
                snapshot["INTERVENTIONS"]["action-id"]["actionProperties"][
                    "description"
                ],
                "<p>Åtgärd & klimat</p>",
            )
            csv_path = convert_snapshot(destination, destination.with_suffix(""))
            with csv_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(actions))
            self.assertEqual(rows[0]["title"], "Åtgärd")
            self.assertEqual(rows[0]["actionProperties.type"], "Styrmedel")
            self.assertEqual(rows[0]["actionProperties.swimlane"], "Beslutat")
            self.assertEqual(rows[0]["actionProperties.actionTags"], "['Sverige']")


if __name__ == "__main__":
    unittest.main()
