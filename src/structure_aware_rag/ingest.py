import json
from pathlib import Path

from structure_aware_rag.chunk import chunk_elements
from structure_aware_rag.parse import partition_document

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")


def ingest_file(path: Path) -> Path:
    elements = partition_document(path)
    chunks = chunk_elements(elements, source_file=path.name)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{path.stem}.json"
    out_path.write_text(
        json.dumps([c.model_dump() for c in chunks], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path


def ingest_all(raw_dir: Path = RAW_DIR) -> list[Path]:
    outputs = []
    for pdf_path in sorted(raw_dir.glob("*.pdf")):
        print(f"Ingesting {pdf_path.name} ...")
        out_path = ingest_file(pdf_path)
        print(f"  -> {out_path}")
        outputs.append(out_path)
    return outputs


if __name__ == "__main__":
    ingest_all()
