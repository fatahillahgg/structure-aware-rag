from uuid import uuid4

from unstructured.documents.elements import Element, Table, Title

from structure_aware_rag.schema import Chunk, ChunkMetadata

MAX_CHARS = 1500


def _heading_path(stack: list[tuple[int, str]]) -> list[str]:
    return [title for _, title in stack]


def chunk_elements(elements: list[Element], source_file: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    heading_stack: list[tuple[int, str]] = []

    buffer_text: list[str] = []
    buffer_types: list[str] = []
    buffer_page: int | None = None

    def flush() -> None:
        nonlocal buffer_page
        if not buffer_text:
            return
        text = "\n\n".join(buffer_text)
        chunks.append(
            Chunk(
                chunk_id=str(uuid4()),
                text=text,
                metadata=ChunkMetadata(
                    source_file=source_file,
                    page_number=buffer_page,
                    heading_path=_heading_path(heading_stack),
                    element_types=list(dict.fromkeys(buffer_types)),
                ),
            )
        )
        buffer_text.clear()
        buffer_types.clear()
        buffer_page = None

    for el in elements:
        depth = getattr(el.metadata, "category_depth", None) or 0
        page = getattr(el.metadata, "page_number", None)

        if isinstance(el, Title):
            flush()
            while heading_stack and heading_stack[-1][0] >= depth:
                heading_stack.pop()
            heading_stack.append((depth, str(el)))
            continue

        # tables are kept as their own standalone chunk (never merged with prose)
        if isinstance(el, Table):
            flush()
            html = getattr(el.metadata, "text_as_html", None) or str(el)
            chunks.append(
                Chunk(
                    chunk_id=str(uuid4()),
                    text=html,
                    metadata=ChunkMetadata(
                        source_file=source_file,
                        page_number=page,
                        heading_path=_heading_path(heading_stack),
                        element_types=["Table"],
                    ),
                )
            )
            continue

        text = str(el)
        if not text.strip():
            continue

        current_len = sum(len(t) for t in buffer_text)
        if current_len + len(text) > MAX_CHARS:
            flush()

        if buffer_page is None:
            buffer_page = page
        buffer_text.append(text)
        buffer_types.append(type(el).__name__)

    flush()
    return chunks
