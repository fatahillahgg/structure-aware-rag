def main() -> None:
    from structure_aware_rag.ingest import ingest_all
    from structure_aware_rag.store import main as store_main

    ingest_all()
    store_main()
