# Structure-Aware RAG Ingestion Pipeline

Pipeline ingestion PDF yang **sadar struktur dokumen** (structure-aware): alih-alih memotong teks per N karakter secara membabi buta, pipeline ini membaca layout dokumen (judul, subjudul, tabel, gambar) lalu membuat chunk yang mempertahankan hierarki heading, nomor halaman, dan tipe elemen. Hasil chunk kemudian di-embed dan disimpan ke **ChromaDB** agar bisa dicari secara semantik.

Dibangun dengan `uv` (package manager Python), [`unstructured`](https://github.com/Unstructured-IO/unstructured) untuk parsing PDF, dan [`chromadb`](https://www.trychroma.com/) sebagai vector store.

---

## Cara Kerja Singkat

```
data/raw/*.pdf
      │  (1) parse layout dengan hi_res + OCR
      ▼
partition_document()  →  daftar Element (Title, NarrativeText, Table, Image, ...)
      │  (2) kelompokkan jadi chunk sadar-struktur
      ▼
chunk_elements()  →  daftar Chunk (text + heading_path + page_number + element_types)
      │  (3) simpan sebagai JSON
      ▼
data/processed/*.json
      │  (4) embed teks & simpan ke Chroma
      ▼
data/chroma/  (vector database, bisa langsung di-query)
```

---

## Struktur Folder

```
Structure Aware RAG/
├── data/
│   ├── raw/          # PDF sumber yang belum diproses — taruh file baru di sini
│   ├── processed/    # Output chunking dalam format JSON (satu file per PDF)
│   └── chroma/        # Vector database ChromaDB (dibuat otomatis, tidak di-commit ke git)
├── src/
│   └── structure_aware_rag/
│       ├── __init__.py      # Entry point `main()` — menjalankan ingest lalu store
│       ├── env_setup.py     # Auto-fix PATH untuk Tesseract OCR & Poppler di Windows
│       ├── parse.py         # Parsing PDF → elemen terstruktur (partition_pdf)
│       ├── chunk.py         # Elemen → chunk sadar-struktur (heading_path, dst.)
│       ├── schema.py        # Model data Pydantic: Chunk & ChunkMetadata
│       ├── ingest.py        # Orkestrasi: baca data/raw/*.pdf → tulis data/processed/*.json
│       └── store.py         # Baca data/processed/*.json → embed & simpan ke ChromaDB
├── ISSUES.md          # Catatan masalah yang diketahui & status perbaikannya
├── pyproject.toml     # Definisi project & dependency (dikelola oleh uv)
└── uv.lock            # Lockfile dependency (jangan diedit manual)
```

### Fungsi Tiap File

| File | Fungsi |
|---|---|
| `src/structure_aware_rag/env_setup.py` | Windows tidak selalu punya Tesseract OCR / Poppler di `PATH` setelah instal via winget. Fungsi `ensure_ocr_tools_on_path()` mendeteksi ini dan menambahkan path instalasi yang diketahui ke `os.environ["PATH"]` secara otomatis sebelum `unstructured` diimpor. |
| `src/structure_aware_rag/parse.py` | Berisi `partition_document(path)` — memanggil `partition_pdf` dari `unstructured` dengan strategi `hi_res` (model deteksi layout + OCR) dan `infer_table_structure=True` supaya tabel terdeteksi sebagai tabel, bukan teks acak. |
| `src/structure_aware_rag/chunk.py` | Otak dari "structure-aware chunking". Berjalan lewat semua elemen hasil parsing dan: <br>• melacak hierarki heading (`Title` + `category_depth`) menjadi `heading_path`, misal `["2 CAUSAL MODELS", "2.1 Contoh"]` <br>• membuang elemen boilerplate (`Header`/`Footer` — running header/footer halaman) <br>• memisahkan konten gambar (`Image`/`FigureCaption`) dari paragraf naratif ke chunk masing-masing <br>• menjaga `Table` selalu jadi chunk tersendiri (disimpan sebagai HTML) <br>• menggabungkan paragraf berurutan hingga batas `MAX_CHARS` (1500 karakter) <br>• membuang chunk yang terlalu pendek (< `MIN_CHARS` = 10 karakter) |
| `src/structure_aware_rag/schema.py` | Model Pydantic `Chunk` (chunk_id, text, metadata) dan `ChunkMetadata` (source_file, page_number, heading_path, element_types) — memastikan struktur output konsisten dan tervalidasi. |
| `src/structure_aware_rag/ingest.py` | Orkestrator tahap parsing: `ingest_all()` mencari semua `*.pdf` di `data/raw/`, memanggil `parse.py` + `chunk.py` untuk masing-masing, lalu menulis hasilnya sebagai `data/processed/<nama-pdf>.json`. |
| `src/structure_aware_rag/store.py` | Orkestrator tahap penyimpanan vektor: `load_chunks()` membaca semua `data/processed/*.json`, `build_collection()` meng-embed teks tiap chunk (model default ChromaDB, `all-MiniLM-L6-v2`, otomatis diunduh) dan menyimpannya ke collection Chroma bernama `documents` di `data/chroma/`. Metadata list (`heading_path`, `element_types`) diratakan jadi string karena Chroma hanya menerima nilai scalar di metadata. |
| `src/structure_aware_rag/__init__.py` | `main()` menjalankan seluruh pipeline end-to-end: ingest semua PDF baru → simpan ke Chroma. Dipanggil lewat `uv run structure-aware-rag`. |

---

## Instalasi

### 1. Prasyarat Sistem (khusus Windows)

Strategi parsing `hi_res` butuh dua tool eksternal untuk membaca PDF yang mengandung gambar/grafik kompleks:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
winget install --id oschwartz10612.Poppler -e
```

> Pipeline sudah otomatis mendeteksi & menambahkan tool ini ke `PATH` saat dijalankan (lihat `env_setup.py`), jadi biasanya **tidak perlu restart terminal**.

### 2. Install Dependency Python

```bash
uv sync
```

Ini akan membuat virtual environment di `.venv/` dan menginstal semua dependency dari `pyproject.toml` (`unstructured[pdf]`, `pydantic`, `chromadb`).

---

## Cara Menjalankan

### Jalankan pipeline lengkap (ingest + simpan ke Chroma)

```bash
uv run structure-aware-rag
```

### Atau jalankan tiap tahap secara terpisah

```bash
# 1. Taruh PDF baru di data/raw/, lalu parse + chunk
uv run python -m structure_aware_rag.ingest

# 2. Embed hasil chunk dan simpan ke ChromaDB
uv run python -m structure_aware_rag.store
```

### Query cepat ke vector store

```python
import chromadb

client = chromadb.PersistentClient(path="data/chroma")
collection = client.get_collection("documents")

hasil = collection.query(query_texts=["apa itu boundary object?"], n_results=3)
for teks, meta in zip(hasil["documents"][0], hasil["metadatas"][0]):
    print(meta["heading_path"], "→", teks[:100])
```

---

## Contoh Output Chunk

Satu chunk di `data/processed/*.json` terlihat seperti ini:

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

`heading_path` inilah yang membuat pipeline ini "structure-aware" — retriever bisa tahu chunk ini berasal dari section apa, bukan sekadar potongan teks tanpa konteks.

---

## Known Issues

Lihat [`ISSUES.md`](./ISSUES.md) untuk daftar masalah yang diketahui (OCR minor artifacts, portabilitas path Tesseract/Poppler di mesin lain, dll.) beserta status perbaikannya.
