# Ingestion Pipeline Issues

> **Update 2026-08-31:** Issues #2 and #4 fixed, #1 partially mitigated, #5 fixed. See "Resolved" section below.

## Completed: Initial Setup
- ✅ PDF parsing with `unstructured[pdf]` + hi_res strategy
- ✅ Structure-aware chunking with heading hierarchy tracking
- ✅ Metadata collection (page, element types, heading path)
- ✅ Output to JSON with chunk IDs and schemas

**Test PDF:** `data/raw/Structural_Causal_Models_as_Boundary_Objects_in_AI_System_Development.pdf` (3 pages)  
**Output:** `data/processed/Structural_Causal_Models_as_Boundary_Objects_in_AI_System_Development.json` (15 chunks)

---

## Known Issues

### 1. OCR Artifacts (Low Priority) — Partially Mitigated
**Problem:** Minor OCR errors in extracted text.

**Examples:**
- "1st" → "Ist" (chunk 0, header) — this was in a `Header` element, now dropped entirely (see #2 fix)
- "Illumination" → "Mluminiation" (chunk 6, text body) — still present, this is a genuine OCR misrecognition, not a ligature/whitespace issue

**Fix applied:** `chunk.py:_clean()` now runs `clean_ligatures` + `clean_extra_whitespace` (from `unstructured.cleaners.core`) on every element's text and on heading titles before they're stored.

**Remaining gap:** True OCR misreads (wrong characters, not ligatures) aren't fixable by cleanup regexes — would need a spellcheck/LLM correction pass, or a higher-DPI re-render before OCR. Left as-is; low priority since it doesn't break structure.

---

### 2. Mixed Element Types in Single Chunk (Medium Priority) — Fixed
**Problem:** Chunks contained heterogeneous element types bundled together (e.g. `NarrativeText + Footer + Image + FigureCaption` in one chunk).

**Fix applied:**
- `Header`/`Footer` elements are now dropped entirely — they're running page boilerplate, not content, and their inclusion is what caused most of the type-mixing.
- `Image`/`FigureCaption` elements are now grouped into their own "figure" chunks, separate from surrounding `NarrativeText`/`Text`/`ListItem` ("narrative" group). The buffer flushes whenever the group changes.

**Verified:** re-ran ingestion — figure chunks are now isolated (e.g. `element_types: ["Image", "FigureCaption"]`), narrative chunks contain only narrative types, and the standalone header-only chunk is gone.

---

### 3. Heading Path Redundancy (Low Priority)
**Problem:** Same `heading_path` repeated across consecutive chunks in same section.

**Example:** Chunks 6-10 all have `heading_path: ["2 CAUSAL MODELS AS BOUNDARY OBJECTS"]`

**Impact:** Low — correct behavior (they *are* in the same section). Useful for section-level filtering in retrieval.

**Fix:** None needed — this is desired behavior for RAG.

---

### 4. System Dependency Management (Infrastructure) — Fixed
**Problem:** Tesseract OCR + Poppler must be on system PATH; no automatic install.

**Fix applied:** `src/structure_aware_rag/env_setup.py:ensure_ocr_tools_on_path()` checks `shutil.which("tesseract")`/`shutil.which("pdftoppm")` and, if missing, injects the known winget install directories into `os.environ["PATH"]` before `unstructured` is imported. Called at the top of `parse.py`.

**Verified:** ran `uv run python -m structure_aware_rag.ingest` in a fresh shell with no manual PATH export — worked.

**Remaining gap:** the candidate install paths in `env_setup.py` are hardcoded to this machine's winget package layout (Tesseract in `Program Files`, Poppler under the winget packages cache with its specific hash-suffixed dir name). Portable across other machines only if they used the same winget install method. Still requires Tesseract/Poppler to be installed via winget (or manually to those exact paths) — doesn't auto-install them.

---

### 5. No Validation of Chunk Quality — Fixed
**Problem:** No checks for empty/whitespace-only chunks, duplicate headings, or malformed metadata.

**Fix applied:** `chunk_elements()` now drops any chunk whose cleaned text is shorter than `MIN_CHARS` (10 chars) before appending it — applies to both narrative/figure chunks and table chunks (empty `text_as_html` is also skipped).

---

## Next Steps (Roadmap)

### Phase 2: Storage & Retrieval
- [ ] Embed chunks with an LLM or sentence-transformer
- [ ] Store in vector DB (Chroma/Qdrant/Pinecone)
- [ ] Implement retriever that uses `heading_path` for hierarchical filtering

### Phase 3: Quality Improvements
- [ ] Fix OCR artifacts (issue #1)
- [ ] Split mixed-type chunks (issue #2)
- [ ] Add chunk validation (issue #5)
- [ ] Automate PATH setup for system deps (issue #4)

### Phase 4: Testing
- [ ] Test on larger PDFs (multi-chapter, complex layouts)
- [ ] Measure chunk size distribution
- [ ] Benchmark retrieval quality

---

## Configuration Notes

**Current chunking strategy:**
- Max chunk size: 1500 characters
- Split on headings: `Title` elements create new chunks
- Tables: always isolated (no merging with prose)
- Heading hierarchy tracked via `category_depth` metadata

**To adjust:**
- Edit `src/structure_aware_rag/chunk.py:MAX_CHARS` for chunk size
- Edit `partition_document()` strategy param (`"fast"`, `"hi_res"`, `"ocr_only"`)
- Modify `heading_stack` logic to control heading-level grouping
