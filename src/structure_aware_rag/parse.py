from pathlib import Path

from unstructured.documents.elements import Element
from unstructured.partition.pdf import partition_pdf


def partition_document(path: Path, strategy: str = "hi_res") -> list[Element]:
    return partition_pdf(
        filename=str(path),
        strategy=strategy,
        infer_table_structure=True,
    )
