# Risks and Assumptions

## Assumptions

- The MVP will support digital PDFs with selectable text.
- Users will upload documents they are authorized to use.
- Gemini API, Pinecone, Supabase, and Render free tiers are sufficient for development and a small demo.
- The system is an information-retrieval assistant, not a legal or compliance certification tool.
- Users understand that answers should be verified using citations.

## Risks

### 1. Poor PDF extraction

Some PDFs contain scanned pages, broken text layers, multi-column layouts, or complex tables.

Mitigation:

- Start with digital PDFs.
- Preserve page references.
- Clearly communicate unsupported scanned-document cases.
- Add OCR later.

### 2. Complex tables

Tables may not extract cleanly from PDFs.

Mitigation:

- Preserve page-level citations.
- Extract table text where possible.
- Add table-specific parsing later.
- Do not claim perfect table support.

### 3. Hallucinated answers

LLMs can generate unsupported claims.

Mitigation:

- Use retrieved evidence only.
- Require citations.
- Add an insufficient-evidence response.
- Evaluate answers using a test dataset.

### 4. Cross-user data leakage

One user must never retrieve another user's documents.

Mitigation:

- Supabase Row Level Security.
- Private storage bucket.
- Verified user identity in FastAPI.
- Pinecone user/tenant namespace and metadata filters.
- Access-control tests.

### 5. Background task failures

Document ingestion can fail due to parsing, API limits, or deployment restarts.

Mitigation:

- Persist ingestion status.
- Store error messages.
- Support retries.
- Move from lightweight background tasks to a worker when needed.

### 6. Free-tier limits

Cloud providers may have quotas, sleep behavior, or changing limits.

Mitigation:

- Use small test documents.
- Avoid unnecessary embedding calls.
- Track usage.
- Design the code so providers can be swapped later.

### 7. Prompt injection in uploaded documents

Documents may contain malicious instructions intended to manipulate the model.

Mitigation:

- Treat documents as untrusted evidence.
- Instruct the model to never follow document instructions.
- Only use documents as factual source material.