"""HTTP tests for the file API in specs/file-upload.md."""

import sqlite3
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from src.project_assistant.api import files as files_api
from src.project_assistant.config import MAX_FILE_SIZE
from src.project_assistant.repositories.files import FileRepository
from src.project_assistant.services.files import FileService
from src.project_assistant.services.llm import LlmError


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class FileUploadApiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = FileRepository(self.root / "data" / "files.sqlite3")
        self.repository.initialize()
        self.service = FileService(self.repository, self.root)

        for target, name, value in (
            (main, "repository", self.repository),
            (files_api, "repository", self.repository),
            (files_api, "service", self.service),
        ):
            active_patch = patch.object(target, name, value)
            active_patch.start()
            self.addCleanup(active_patch.stop)

        self.client = TestClient(main.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def upload(self, *items):
        with ExitStack() as opened_files:
            files = []
            for filename, source in items:
                content = opened_files.enter_context(source.open("rb")) if isinstance(source, Path) else source
                files.append(("files", (filename, content, "text/plain")))
            return self.client.post("/files", files=files)

    def test_fu01_batch_upload_persists_files_and_metadata_without_llm(self):
        with patch.object(files_api, "generate_metadata") as generator:
            response = self.upload(("first.txt", FIXTURES / "first.txt"),
                                   ("second.MD", FIXTURES / "second.MD"))
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item["success"] for item in items))
        self.assertEqual((self.service.upload_dir / "first.txt").read_bytes(),
                         (FIXTURES / "first.txt").read_bytes())
        self.assertEqual((self.service.upload_dir / "second.MD").read_bytes(),
                         (FIXTURES / "second.MD").read_bytes())
        self.assertEqual(self.repository.get(items[1]["id"])["file_type"], "md")
        self.assertEqual(self.repository.get(items[0]["id"])["file_path"], "data/uploads/first.txt")
        generator.assert_not_called()

    def test_fu02_no_files_returns_400(self):
        response = self.client.post("/files")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "NO_FILES")

    def test_fu03_invalid_items_do_not_stop_valid_file(self):
        response = self.upload(("unsupported.csv", FIXTURES / "unsupported.csv"),
                               ("../escape.txt", FIXTURES / "first.txt"),
                               ("CON.md", FIXTURES / "note.md"),
                               ("good.md", FIXTURES / "note.md"))
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual([item.get("error_code") for item in items[:3]], [
            "UNSUPPORTED_FILE_TYPE", "INVALID_FILENAME", "INVALID_FILENAME",
        ])
        self.assertTrue(items[3]["success"])
        self.assertEqual([item["stored_filename"] for item in self.repository.list()], ["good.md"])

    def test_fu04_size_boundary_and_rejected_file_cleanup(self):
        response = self.upload(("limit.txt", FIXTURES / "limit.txt"),
                               ("too-large.txt", FIXTURES / "too-large.txt"))
        self.assertEqual(response.status_code, 200)
        accepted, rejected = response.json()["items"]
        self.assertTrue(accepted["success"])
        self.assertEqual(accepted["file_size"], MAX_FILE_SIZE)
        self.assertEqual(rejected["error_code"], "FILE_TOO_LARGE")
        self.assertFalse((self.service.upload_dir / "too-large.txt").exists())
        self.assertEqual(len(self.repository.list()), 1)

    def test_fu05_duplicate_name_never_overwrites_existing_file(self):
        self.service.upload_dir.mkdir(parents=True)
        (self.service.upload_dir / "note.md").write_bytes((FIXTURES / "note.md").read_bytes())
        response = self.upload(("note.md", FIXTURES / "note.md"),
                               ("note.md", FIXTURES / "note.md"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["stored_filename"] for item in response.json()["items"]],
                         ["note_1.md", "note_2.md"])
        self.assertEqual((self.service.upload_dir / "note.md").read_bytes(),
                         (FIXTURES / "note.md").read_bytes())
        self.assertEqual((self.service.upload_dir / "note_1.md").read_bytes(),
                         (FIXTURES / "note.md").read_bytes())

    def test_fu06_index_write_failure_removes_uploaded_file(self):
        with patch.object(self.repository, "add", side_effect=sqlite3.OperationalError("locked")):
            response = self.upload(("note.md", FIXTURES / "note.md"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["error_code"], "INDEX_SAVE_FAILED")
        self.assertEqual(list(self.service.upload_dir.iterdir()), [])

    def test_fu07_save_failure_is_reported_per_file(self):
        self.service.upload_dir.parent.mkdir(parents=True, exist_ok=True)
        self.service.upload_dir.write_bytes((FIXTURES / "first.txt").read_bytes())
        response = self.upload(("note.md", FIXTURES / "note.md"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["error_code"], "SAVE_FAILED")
        self.assertEqual(self.repository.list(), [])

    def test_fu08_list_and_detail_return_only_metadata(self):
        first_id = self.upload(("first.txt", FIXTURES / "first.txt")).json()["items"][0]["id"]
        second_id = self.upload(("second.md", FIXTURES / "second.MD")).json()["items"][0]["id"]
        response = self.client.get("/files")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["items"]], [second_id, first_id])
        self.assertNotIn((FIXTURES / "first.txt").read_text(encoding="utf-8").strip(), response.text)
        detail = self.client.get(f"/files/{first_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["keywords"], [])
        self.assertNotIn((FIXTURES / "first.txt").read_text(encoding="utf-8").strip(), detail.text)
        missing = self.client.get("/files/999999")
        self.assertEqual((missing.status_code, missing.json()["error_code"]),
                         (404, "FILE_NOT_FOUND"))

    def test_fu09_patch_updates_only_supplied_metadata_fields(self):
        file_id = self.upload(("note.md", FIXTURES / "note.md")).json()["items"][0]["id"]
        summary = self.client.patch(f"/files/{file_id}/metadata", json={"summary": "my summary"})
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["summary_source"], "user")
        self.assertIsNone(summary.json()["keywords_source"])
        keywords = self.client.patch(f"/files/{file_id}/metadata",
                                     json={"keywords": ["Python", "上传"]})
        self.assertEqual(keywords.status_code, 200)
        self.assertEqual(keywords.json()["summary"], "my summary")
        self.assertEqual(keywords.json()["keywords"], ["Python", "上传"])
        self.assertEqual(keywords.json()["keywords_source"], "user")
        self.assertEqual(self.client.patch("/files/999999/metadata", json={}).status_code, 404)
        self.assertEqual(self.client.patch(f"/files/{file_id}/metadata",
                                           json={"keywords": "not an array"}).status_code, 422)

    def test_fu10_index_sends_body_only_on_request_and_keeps_user_values(self):
        file_id = self.upload(("note.md", FIXTURES / "note.md")).json()["items"][0]["id"]
        self.client.patch(f"/files/{file_id}/metadata", json={"summary": "mine"})
        with patch.object(files_api, "generate_metadata", return_value=("generated", ["tag"])) as generator:
            response = self.client.post(f"/files/{file_id}/index")
        self.assertEqual(response.status_code, 200)
        generator.assert_called_once_with((FIXTURES / "note.md").read_text(encoding="utf-8"))
        self.assertEqual(response.json()["summary"], "mine")
        self.assertEqual(response.json()["summary_source"], "user")
        self.assertEqual(response.json()["keywords"], ["tag"])
        self.assertEqual(response.json()["keywords_source"], "llm")

    def test_fu11_llm_failure_does_not_change_metadata(self):
        file_id = self.upload(("note.md", FIXTURES / "note.md")).json()["items"][0]["id"]
        self.client.patch(f"/files/{file_id}/metadata", json={"summary": "mine"})
        before = self.client.get(f"/files/{file_id}").json()
        with patch.object(files_api, "generate_metadata", side_effect=LlmError("failed")):
            response = self.client.post(f"/files/{file_id}/index")
        self.assertEqual((response.status_code, response.json()["error_code"]),
                         (502, "LLM_FAILED"))
        self.assertEqual(self.client.get(f"/files/{file_id}").json(), before)
        self.assertEqual(self.client.post("/files/999999/index").status_code, 404)

    def test_fu12_empty_text_file_is_stored(self):
        response = self.upload(("empty.txt", FIXTURES / "empty.txt"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["file_size"], 0)
        self.assertEqual((self.service.upload_dir / "empty.txt").read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
