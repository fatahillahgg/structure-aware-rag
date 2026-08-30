# Structure-Aware RAG Ingestion Pipeline

Kebanyakan pipeline RAG memotong dokumen per N karakter tanpa peduli isinya —
kalimat bisa terpotong di tengah, tabel bisa hancur jadi teks acak, dan
konteks section-nya hilang. Pipeline ini coba beda: baca dulu layout PDF-nya
(judul, subjudul, tabel, gambar), baru bikin chunk yang tetap tahu dia ada di
section mana, di halaman berapa, dan berbentuk apa.

Prosesnya dua tahap. PDF diparsing pakai
[`unstructured`](https://github.com/Unstructured-IO/unstructured), hasilnya
dikelompokkan jadi chunk sadar-struktur, lalu di-embed dan disimpan ke
[`ChromaDB`](https://www.trychroma.com/) supaya bisa dicari secara semantik.
Package manager-nya `uv`.

## Alurnya

```
data/raw/*.pdf
      │  parse layout (hi_res + OCR)
      ▼
partition_document()  →  Title, NarrativeText, Table, Image, ...
      │  kelompokkan jadi chunk, sambil lacak heading & halaman
      ▼
chunk_elements()  →  Chunk (text, heading_path, page_number, element_types)
      │  tulis ke JSON
      ▼
data/processed/*.json
      │  embed & simpan
      ▼
data/chroma/  (vector db, siap di-query)
```

## Struktur Folder

```
Structure Aware RAG/
├── data/
│   ├── raw/          # PDF sumber — taruh file baru di sini
│   ├── processed/    # Output chunking, satu JSON per PDF
│   └── chroma/       # Vector db, dibuat otomatis, tidak ikut di-commit
├── src/structure_aware_rag/
│   ├── __init__.py   # main() — jalanin ingest lalu store
│   ├── env_setup.py  # nambal PATH kalau Tesseract/Poppler belum kedetect
│   ├── parse.py      # PDF → elemen terstruktur
│   ├── chunk.py       # elemen → chunk sadar-struktur, ini intinya
│   ├── schema.py      # model Pydantic buat Chunk & metadata-nya
│   ├── ingest.py      # baca data/raw/*.pdf, tulis data/processed/*.json
│   └── store.py       # baca data/processed/*.json, embed, simpan ke Chroma
├── ISSUES.md          # masalah yang udah ketemu, mana yang udah/belum dibenerin
├── pyproject.toml
└── uv.lock
```

Yang paling penting dibaca duluan kalau mau ngerti pipeline-nya ya
`chunk.py` — di situ semua logika "structure-aware"-nya kejadian.

## Isi tiap file

**`env_setup.py`** — hi_res strategy butuh Tesseract OCR dan Poppler, dan di
Windows dua ini sering nggak nongol di `PATH` walau udah keinstall lewat
winget (apalagi kalau terminal-nya udah kebuka duluan sebelum instalasi).
`ensure_ocr_tools_on_path()` ngecek dulu pakai `shutil.which`, kalau nggak
ketemu baru dia tambahin path instalasi yang dikenal ke `os.environ["PATH"]`
sebelum `unstructured` di-import. Jadi nggak perlu restart terminal.

**`parse.py`** — `partition_document(path)` motor sederhana ke
`partition_pdf` dari `unstructured` pakai strategy `hi_res` (model deteksi
layout, bukan cuma extract text mentah) dan `infer_table_structure=True`
biar tabel kedeteksi sebagai tabel, bukan barisan teks yang berantakan.

**`chunk.py`** — inti pipeline. Loop lewat semua elemen hasil parsing, dan:
- lacak hierarki heading (`Title` + `category_depth`-nya) jadi `heading_path`,
  misal `["2 CAUSAL MODELS", "2.1 Contoh"]`
- buang elemen `Header`/`Footer` — ini running header/footer halaman, bukan
  konten, cuma nambah noise
- pisahin `Image`/`FigureCaption` dari paragraf narasi ke chunk sendiri,
  biar nggak nyampur
- `Table` selalu jadi chunk sendiri, disimpan sebagai HTML (bukan teks polos)
- gabungin paragraf berurutan sampai batas `MAX_CHARS` (1500 karakter)
- buang chunk yang kependekan (di bawah `MIN_CHARS` = 10 karakter, biasanya
  sisa noise)

**`schema.py`** — model Pydantic `Chunk` dan `ChunkMetadata`, biar strukturnya
konsisten dan gampang divalidasi.

**`ingest.py`** — orkestrasi tahap parsing. `ingest_all()` cari semua PDF di
`data/raw/`, proses satu-satu lewat `parse.py` + `chunk.py`, tulis hasilnya
ke `data/processed/<nama-pdf>.json`.

**`store.py`** — orkestrasi tahap penyimpanan. `load_chunks()` baca semua
JSON di `data/processed/`, `build_collection()` embed teksnya (model default
Chroma, `all-MiniLM-L6-v2`, download otomatis pas pertama jalan) dan simpan
ke collection `documents` di `data/chroma/`. Field list kayak `heading_path`
diratain jadi string dulu karena Chroma cuma nerima metadata scalar.

**`__init__.py`** — `main()` jalanin semuanya: ingest PDF baru, terus simpan
ke Chroma. Dipanggil lewat `uv run structure-aware-rag`.

## Instalasi

### 1. Dependency sistem (Windows)

`hi_res` butuh dua tool eksternal buat baca PDF yang ada gambar/grafik:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
winget install --id oschwartz10612.Poppler -e
```

Nggak perlu restart terminal — `env_setup.py` udah nge-handle itu otomatis.

### 2. Dependency Python

```bash
uv sync
```

Bikin `.venv/` dan install semua dari `pyproject.toml`.

## Cara Pakai

Jalanin semuanya sekaligus:

```bash
uv run structure-aware-rag
```

Atau per tahap, kalau lagi mau ngecek satu bagian aja:

```bash
uv run python -m structure_aware_rag.ingest   # parse + chunk
uv run python -m structure_aware_rag.store    # embed + simpan ke Chroma
```

Nge-query langsung ke vector store:

```python
import chromadb

client = chromadb.PersistentClient(path="data/chroma")
collection = client.get_collection("documents")

hasil = collection.query(query_texts=["apa itu boundary object?"], n_results=3)
for teks, meta in zip(hasil["documents"][0], hasil["metadatas"][0]):
    print(meta["heading_path"], "→", teks[:100])
```

## Contoh output

Satu chunk di `data/processed/*.json`:

```json
{
  "chunk_id": "b9a53cb6-2253-42e0-96da-ddf225437ff5",
  "text": "\"Boundary objects are objects which are both plastic enough to adapt to local needs...\"",
  "metadata": {
    "source_file": "Structural_Causal_Models_as_Boundary_Objects_in_AI_System_Development.pdf",
    "page_number": 2,
    "heading_path": ["3 CONCLUSION"],
    "element_types": ["NarrativeText"]
  }
}
```

`heading_path` ini yang bikin pipeline-nya kebilang "structure-aware" —
retriever jadi tahu chunk ini dari section mana, bukan cuma potongan teks
lepas tanpa konteks.

## Known Issues

Cek [`ISSUES.md`](./ISSUES.md) — ada catatan soal artefak minor dari OCR dan
portabilitas path Tesseract/Poppler di mesin lain.
