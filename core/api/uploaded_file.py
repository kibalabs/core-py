from pydantic import BaseModel


class UploadedFile(BaseModel):
    filename: str | None
    contentType: str | None
    content: bytes
