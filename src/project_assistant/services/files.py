import re
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile

from src.project_assistant.config import MAX_FILE_SIZE, PROJECT_ROOT
from src.project_assistant.repositories.files import FileRepository


RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                  *(f"LPT{i}" for i in range(1, 10))}


class FileService:
    def __init__(self, repository: FileRepository, project_root: Path = PROJECT_ROOT,
                 upload_dir: Path | None = None):
        self.repository = repository
        self.project_root = project_root
        self.upload_dir = upload_dir or project_root / "data" / "uploads"

    @staticmethod
    def _validate_filename(filename: str):
        if (not filename or len(filename) > 240 or filename in {".", ".."}
                or filename[-1] in " ."
                or re.search(r'[\\/:*?"<>|\x00-\x1f]', filename)
                or filename.split(".", 1)[0].upper() in RESERVED_NAMES):
            return "INVALID_FILENAME", "The filename is invalid or unsafe."
        if Path(filename).suffix.lower() not in {".txt", ".md"}:
            return "UNSUPPORTED_FILE_TYPE", "Only .txt and .md files are supported."
        return None

    def upload(self, upload: UploadFile):
        filename = upload.filename or ""
        failure = self._validate_filename(filename)
        if failure:
            return self._failure(filename, *failure)

        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            data_dir = self.project_root / "data"
            if (data_dir.is_symlink() or self.upload_dir.is_symlink()
                    or data_dir.resolve().parent != self.project_root.resolve()
                    or self.upload_dir.resolve().parent != data_dir.resolve()):
                raise OSError("Unsafe upload directory")
            stem = Path(filename).stem
            extension = Path(filename).suffix
            number = 0
            while True:
                stored_filename = filename if number == 0 else f"{stem}_{number}{extension}"
                target = self.upload_dir / stored_filename
                try:
                    output = target.open("xb")
                    break
                except FileExistsError:
                    number += 1
            size = 0
            try:
                with output:
                    while chunk := upload.file.read(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_FILE_SIZE:
                            raise FileTooLargeError
                        output.write(chunk)
            except Exception:
                target.unlink(missing_ok=True)
                raise
        except FileTooLargeError:
            return self._failure(filename, "FILE_TOO_LARGE", "The file exceeds 10 MB.")
        except OSError:
            return self._failure(filename, "SAVE_FAILED", "Could not save the file.")

        file_path = target.relative_to(self.project_root).as_posix()
        try:
            file_id = self.repository.add(
                filename, stored_filename, file_path, extension[1:].lower(),
                size, datetime.now().astimezone().isoformat(),
            )
        except sqlite3.Error:
            target.unlink(missing_ok=True)
            return self._failure(filename, "INDEX_SAVE_FAILED", "Could not save the file index.")
        return {"success": True, "id": file_id, "original_filename": filename,
                "stored_filename": stored_filename, "file_size": size}

    @staticmethod
    def _failure(filename, code, message):
        return {"success": False, "original_filename": filename,
                "error_code": code, "message": message}

    def body_for_index(self, item):
        data_dir = self.project_root / "data"
        if (data_dir.is_symlink() or self.upload_dir.is_symlink()
                or self.upload_dir.resolve().parent != data_dir.resolve()):
            raise OSError("Unsafe upload directory")
        path = self.upload_dir / item["stored_filename"]
        if path.is_symlink() or path.resolve().parent != self.upload_dir.resolve():
            raise OSError("Unsafe file location")
        with path.open("rb") as source:
            content = source.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            raise OSError("File size changed after upload")
        return content.decode("utf-8")


class FileTooLargeError(Exception):
    pass
