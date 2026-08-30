from pathlib import Path

from structure_aware_rag.env_setup import ensure_ocr_tools_on_path

ensure_ocr_tools_on_path()

from unstructured.documents.elements import Element  # noqa: E402
from unstructured.partition.pdf import partition_pdf  # noqa: E402


def partition_document(path: Path, strategy: str = "hi_res") -> list[Element]:
    return partition_pdf(
        filename=str(path),
        strategy=strategy,
        infer_table_structure=True,
    )
