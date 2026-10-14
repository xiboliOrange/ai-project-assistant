import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile

from src.project_assistant.config import MAX_FILE_SIZE
from src.project_assistant.repositories.files import FileRepository
from src.project_assistant.services.files import FileService


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class FileServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = FileRepository(self.root / "data" / "files.sqlite3")
        self.repository.initialize()
        self.service = FileService(self.repository, self.root)

    @staticmethod
    def upload(filename, source):
        content = source.read_bytes() if isinstance(source, Path) else source
        return UploadFile(file=io.BytesIO(content), filename=filename)

    def test_upload_duplicate_and_metadata(self):
        first = self.service.upload(self.upload("note.MD", FIXTURES / "first.txt"))
        second = self.service.upload(self.upload("note.MD", FIXTURES / "second.MD"))
        self.assertEqual(first["stored_filename"], "note.MD")
        self.assertEqual(second["stored_filename"], "note_1.MD")
        self.assertEqual((self.service.upload_dir / "note.MD").read_bytes(),
                         (FIXTURES / "first.txt").read_bytes())
        items = self.repository.list()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], second["id"])
        self.assertEqual(items[0]["file_path"], "data/uploads/note_1.MD")
        self.assertEqual(items[0]["keywords"], [])

    def test_invalid_large_and_valid_items_are_independent(self):
        results = [
            self.service.upload(self.upload("unsupported.csv", FIXTURES / "unsupported.csv")),
            self.service.upload(self.upload("../bad.txt", FIXTURES / "first.txt")),
            self.service.upload(self.upload("CON.txt", FIXTURES / "first.txt")),
            self.service.upload(self.upload("large.txt", FIXTURES / "too-large.txt")),
            self.service.upload(self.upload("good.txt", FIXTURES / "first.txt")),
        ]
        self.assertEqual([item.get("error_code") for item in results[:4]], [
            "UNSUPPORTED_FILE_TYPE", "INVALID_FILENAME", "INVALID_FILENAME", "FILE_TOO_LARGE"
        ])
        self.assertTrue(results[4]["success"])
        self.assertEqual([path.name for path in self.service.upload_dir.iterdir()], ["good.txt"])
        self.assertEqual(len(self.repository.list()), 1)

    def test_database_failure_removes_new_file(self):
        with patch.object(self.repository, "add", side_effect=sqlite3.OperationalError("locked")):
            result = self.service.upload(self.upload("note.md", FIXTURES / "note.md"))
        self.assertEqual(result["error_code"], "INDEX_SAVE_FAILED")
        self.assertEqual(list(self.service.upload_dir.iterdir()), [])

    def test_exact_size_limit_is_accepted(self):
        result = self.service.upload(self.upload("limit.txt", FIXTURES / "limit.txt"))
        self.assertTrue(result["success"])
        self.assertEqual(result["file_size"], MAX_FILE_SIZE)

    def test_user_values_are_preserved_during_llm_update(self):
        file_id = self.service.upload(self.upload("note.md", FIXTURES / "note.md"))["id"]
        self.repository.update_user(file_id, {"summary": "my summary"})
        item = self.repository.update_llm(file_id, "generated", ["first"])
        self.assertEqual(item["summary"], "my summary")
        self.assertEqual(item["summary_source"], "user")
        self.assertEqual(item["keywords"], ["first"])
        self.repository.update_user(file_id, {"keywords": ["mine"]})
        item = self.repository.update_llm(file_id, "another", ["another"])
        self.assertEqual(item["keywords"], ["mine"])
        self.assertEqual(item["keywords_source"], "user")


if __name__ == "__main__":
    unittest.main()
