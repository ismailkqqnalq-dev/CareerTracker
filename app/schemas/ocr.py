from pydantic import BaseModel


class OcrExtractResponse(BaseModel):
    text: str
    width: int
    height: int
    image_format: str
