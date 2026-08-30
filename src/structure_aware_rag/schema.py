from pydantic import BaseModel


class ChunkMetadata(BaseModel):
    source_file: str
    page_number: int | None = None
    heading_path: list[str] = []
    element_types: list[str] = []


class Chunk(BaseModel):
    chunk_id: str
    text: str
    metadata: ChunkMetadata
