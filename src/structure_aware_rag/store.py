import json
from pathlib import Path

import chromadb

PROCESSED_DIR = Path("data/processed")
CHROMA_DIR = Path("data/chroma")
COLLECTION_NAME = "documents"


def _flatten_metadata(metadata: dict) -> dict:
    """Chroma metadata values must be str/int/float/bool, so list fields are
    joined into delimited strings rather than stored as nested lists."""
    return {
        "source_file": metadata["source_file"],
        "page_number": metadata["page_number"] if metadata["page_number"] is not None else -1,
        "heading_path": " > ".join(metadata["heading_path"]),
        "element_types": ",".join(metadata["element_types"]),
    }


def load_chunks(processed_dir: Path = PROCESSED_DIR) -> list[dict]:
    chunks = []
    for json_path in sorted(processed_dir.glob("*.json")):
        chunks.extend(json.loads(json_path.read_text(encoding="utf-8")))
    return chunks


def build_collection(chunks: list[dict], persist_dir: Path = CHROMA_DIR):
    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(COLLECTION_NAME)

    if not chunks:
        return collection

    collection.upsert(
        ids=[c["chunk_id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[_flatten_metadata(c["metadata"]) for c in chunks],
    )
    return collection


def main() -> None:
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks from {PROCESSED_DIR}")
    collection = build_collection(chunks)
    print(f"Collection '{COLLECTION_NAME}' now has {collection.count()} items in {CHROMA_DIR}")


if __name__ == "__main__":
    main()
