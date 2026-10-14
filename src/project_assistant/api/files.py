import sqlite3

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, model_validator

from src.project_assistant.config import DATABASE_PATH
from src.project_assistant.errors import api_error
from src.project_assistant.repositories.files import FileRepository
from src.project_assistant.services.files import FileService
from src.project_assistant.services.llm import LlmError, generate_metadata


router = APIRouter(prefix="/files", tags=["files"])
repository = FileRepository(DATABASE_PATH)
service = FileService(repository)


class MetadataPatch(BaseModel):
    summary: str | None = None
    keywords: list[str] | None = None

    @model_validator(mode="after")
    def validate_keywords(self):
        if "keywords" in self.model_fields_set and self.keywords is None:
            raise ValueError("keywords must be an array of strings")
        return self


@router.post("")
def upload_files(files: list[UploadFile] | None = File(default=None)):
    if not files:
        raise api_error(400, "NO_FILES", "At least one file is required.")
    return {"items": [service.upload(upload) for upload in files]}


@router.get("")
def list_files():
    return {"items": repository.list()}


@router.get("/{file_id}")
def get_file(file_id: int):
    item = repository.get(file_id)
    if item is None:
        raise api_error(404, "FILE_NOT_FOUND", "The file does not exist.")
    return item


@router.patch("/{file_id}/metadata")
def patch_metadata(file_id: int, patch: MetadataPatch):
    if repository.get(file_id) is None:
        raise api_error(404, "FILE_NOT_FOUND", "The file does not exist.")
    try:
        return repository.update_user(file_id, patch.model_dump(exclude_unset=True))
    except sqlite3.Error:
        raise api_error(500, "INDEX_SAVE_FAILED", "Could not save file metadata.")


@router.post("/{file_id}/index")
def index_file(file_id: int):
    item = repository.get(file_id)
    if item is None:
        raise api_error(404, "FILE_NOT_FOUND", "The file does not exist.")
    try:
        body = service.body_for_index(item)
        summary, keywords = generate_metadata(body)
        return repository.update_llm(file_id, summary, keywords)
    except sqlite3.Error:
        raise api_error(500, "INDEX_SAVE_FAILED", "Could not save file metadata.")
    except (OSError, UnicodeError, LlmError):
        raise api_error(502, "LLM_FAILED", "Could not generate file metadata.")
