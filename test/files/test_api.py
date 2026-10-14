import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

from src.project_assistant.api import files as files_api
from src.project_assistant.repositories.files import FileRepository
from src.project_assistant.services.files import FileService
from src.project_assistant.services.llm import LlmError


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class FileApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        repository = FileRepository(root / "data" / "files.sqlite3")
        repository.initialize()
        self.addCleanup(patch.stopall)
        patch.object(files_api, "repository", repository).start()
        patch.object(files_api, "service", FileService(repository, root)).start()

    def test_batch_query_patch_and_index(self):
        files = [UploadFile(file=io.BytesIO((FIXTURES / "note.md").read_bytes()), filename="note.md"),
                 UploadFile(file=io.BytesIO((FIXTURES / "unsupported.csv").read_bytes()),
                            filename="unsupported.csv")]
        results = files_api.upload_files(files)["items"]
        self.assertTrue(results[0]["success"])
        self.assertEqual(results[1]["error_code"], "UNSUPPORTED_FILE_TYPE")
        file_id = results[0]["id"]
        self.assertEqual(len(files_api.list_files()["items"]), 1)
        item = files_api.patch_metadata(file_id, files_api.MetadataPatch(summary="mine"))
        self.assertEqual(item["summary_source"], "user")
        with patch.object(files_api, "generate_metadata", return_value=("generated", ["tag"])):
            item = files_api.index_file(file_id)
        self.assertEqual(item["summary"], "mine")
        self.assertEqual(item["keywords"], ["tag"])

    def test_missing_files_and_missing_id(self):
        with self.assertRaises(HTTPException) as missing_files:
            files_api.upload_files([])
        self.assertEqual(missing_files.exception.detail["error_code"], "NO_FILES")
        with self.assertRaises(HTTPException) as missing_id:
            files_api.get_file(999)
        self.assertEqual(missing_id.exception.detail["error_code"], "FILE_NOT_FOUND")

    def test_llm_failure_preserves_metadata(self):
        file_id = files_api.upload_files([
            UploadFile(file=io.BytesIO((FIXTURES / "note.md").read_bytes()), filename="note.md")
        ])["items"][0]["id"]
        files_api.patch_metadata(file_id, files_api.MetadataPatch(summary="mine"))
        with patch.object(files_api, "generate_metadata", side_effect=LlmError("failed")):
            with self.assertRaises(HTTPException) as failure:
                files_api.index_file(file_id)
        self.assertEqual(failure.exception.detail["error_code"], "LLM_FAILED")
        self.assertEqual(files_api.get_file(file_id)["summary"], "mine")


if __name__ == "__main__":
    unittest.main()
