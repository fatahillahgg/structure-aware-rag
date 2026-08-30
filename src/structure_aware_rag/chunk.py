from uuid import NAMESPACE_URL, uuid5

from unstructured.cleaners.core import clean_extra_whitespace, clean_ligatures
from unstructured.documents.elements import Element, Footer, Header, Table, Title

from structure_aware_rag.schema import Chunk, ChunkMetadata

MAX_CHARS = 1500
MIN_CHARS = 10

# Boilerplate elements carry no retrievable content (running page headers/footers).
_SKIP_TYPES = (Header, Footer)

# Figure-related elements are kept in their own chunk, separate from surrounding
# prose, so a retriever can tell "this is figure context" from "this is body text".
_FIGURE_TYPES = ("Image", "FigureCaption")


def _heading_path(stack: list[tuple[int, str]]) -> list[str]:
    return [title for _, title in stack]


def _group(el: Element) -> str:
    return "figure" if type(el).__name__ in _FIGURE_TYPES else "narrative"


def _clean(text: str) -> str:
    return clean_extra_whitespace(clean_ligatures(text))


def _chunk_id(source_file: str, index: int) -> str:
    """Deterministic (not random) so re-ingesting the same PDF reproduces the
    same IDs and a Chroma upsert overwrites in place instead of duplicating."""
    return str(uuid5(NAMESPACE_URL, f"{source_file}#{index}"))


def chunk_elements(elements: list[Element], source_file: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    heading_stack: list[tuple[int, str]] = []

    buffer_text: list[str] = []
    buffer_types: list[str] = []
    buffer_page: int | None = None
    buffer_group: str | None = None

    def flush() -> None:
        nonlocal buffer_page, buffer_group
        if not buffer_text:
            return
        text = "\n\n".join(buffer_text).strip()
        if len(text) >= MIN_CHARS:
            chunks.append(
                Chunk(
                    chunk_id=_chunk_id(source_file, len(chunks)),
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
        buffer_group = None

    for el in elements:
        if isinstance(el, _SKIP_TYPES):
            continue

        depth = getattr(el.metadata, "category_depth", None) or 0
        page = getattr(el.metadata, "page_number", None)

        if isinstance(el, Title):
            flush()
            while heading_stack and heading_stack[-1][0] >= depth:
                heading_stack.pop()
            heading_stack.append((depth, _clean(str(el))))
            continue

        # tables are kept as their own standalone chunk (never merged with prose)
        if isinstance(el, Table):
            flush()
            html = getattr(el.metadata, "text_as_html", None) or str(el)
            if html.strip():
                chunks.append(
                    Chunk(
                        chunk_id=_chunk_id(source_file, len(chunks)),
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

        text = _clean(str(el))
        if not text.strip():
            continue

        group = _group(el)
        current_len = sum(len(t) for t in buffer_text)
        if buffer_group is not None and (group != buffer_group or current_len + len(text) > MAX_CHARS):
            flush()

        if buffer_page is None:
            buffer_page = page
        buffer_group = group
        buffer_text.append(text)
        buffer_types.append(type(el).__name__)

    flush()
    return chunks
