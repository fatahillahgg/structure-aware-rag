# Ingestion Pipeline Issues

## Completed: Initial Setup
- ✅ PDF parsing with `unstructured[pdf]` + hi_res strategy
- ✅ Structure-aware chunking with heading hierarchy tracking
- ✅ Metadata collection (page, element types, heading path)
- ✅ Output to JSON with chunk IDs and schemas

**Test PDF:** `data/raw/Structural_Causal_Models_as_Boundary_Objects_in_AI_System_Development.pdf` (3 pages)  
**Output:** `data/processed/Structural_Causal_Models_as_Boundary_Objects_in_AI_System_Development.json` (15 chunks)

---

## Known Issues

### 1. OCR Artifacts (Low Priority)
**Problem:** Minor OCR errors in extracted text.

**Examples:**
- "1st" → "Ist" (chunk 0, header)
- "Illumination" → "Mluminiation" (chunk 6, text body)

**Impact:** Low — doesn't break structure, just noise in text field.

**Fix:**
- Post-process with regex to fix common OCR patterns (e.g., `Mluminiation` → `Illumination`)
- Or: switch to larger OCR confidence threshold if unstructured library supports it

---

### 2. Mixed Element Types in Single Chunk (Medium Priority)
**Problem:** Chunks contain heterogeneous element types bundled together.

**Example:** Chunk 7 (Figure 1 context):
```json
"element_types": ["NarrativeText", "Text", "Footer", "Image", "FigureCaption"]
```

**Impact:** Medium — makes it harder for downstream systems to filter by type (e.g., "give me only text chunks, exclude images"). Single-type chunks are cleaner for RAG.

**Fix:**
- Modify `chunk.py:chunk_elements()` to split chunks when element type changes
- Option A: One chunk per element type (more fragmented but clean)
- Option B: Keep mixed types but separate them into sub-lists in metadata (preserve context while allowing filtering)

---

### 3. Heading Path Redundancy (Low Priority)
**Problem:** Same `heading_path` repeated across consecutive chunks in same section.

**Example:** Chunks 6-10 all have `heading_path: ["2 CAUSAL MODELS AS BOUNDARY OBJECTS"]`

**Impact:** Low — correct behavior (they *are* in the same section). Useful for section-level filtering in retrieval.

**Fix:** None needed — this is desired behavior for RAG.

---

### 4. System Dependency Management (Infrastructure)
**Problem:** Tesseract OCR + Poppler must be on system PATH; no automatic install.

**Current workaround:**
```bash
export PATH="/c/Program Files/Tesseract-OCR:..." && uv run ...
```

**Fix:**
- Add PATH setup to `.env` or shell initialization
- Or: use `os.environ["PATH"]` in Python code to inject paths at runtime
- Or: document in README that `tesseract` and `poppler` must be installed via `winget`

---

### 5. No Validation of Chunk Quality
**Problem:** No checks for empty/whitespace-only chunks, duplicate headings, or malformed metadata.

**Fix:**
- Add `chunk_elements()` post-processing to validate and filter bad chunks
- e.g., reject chunks where `text.strip() == ""` or `len(text) < 10`

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
