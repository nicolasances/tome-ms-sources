# Source Knowledge Extraction — Feature Spec

## Overview

This spec defines how `tome-ms-sources` enables the **Language Learning** use-case of Tome by:

1. **Persisting Data Sources** — storing metadata about a user's learning material (e.g. a Google Doc) in MongoDB.
2. **Extracting Knowledge** — on demand, fetching the raw text from the source, using two parallel LLM agents (LangChain) to extract:
   - **Vocabulary pairs** (words and translations), pushed to `tome-ms-language`.
   - **Sentences** (phrases and translations found in the source material), also pushed to `tome-ms-language`.

The overall user journey is:

> The user registers a Google Doc as a Data Source, then manually triggers extraction. Extraction reads the document, extracts word-translation pairs and sentence-translation pairs, and inserts them into the respective stores in `tome-ms-language`.

This matches the two-step model described in the [Data Sources in Language Learning](https://github.com/nicolasances/tome/blob/main/docs/capabilities/language/data-sources.md) product doc: **Add** is separate from **Fetch & Process**.

> **Note on repeated extraction:** Triggering extraction more than once on the same source is safe to do — the workflow will re-read the current document and push the results each time. However, because `tome-ms-language` does not deduplicate, repeated extractions will insert duplicate vocabulary or sentence entries. This is acceptable; deduplication is out of scope for this spec.

---

## Data Model — Data Source

Data Sources are persisted in a MongoDB collection named **`sources`**, in the **`tomesources`** database.

| Field             | Type             | Description                                                              |
|-------------------|------------------|--------------------------------------------------------------------------|
| `id`              | string           | MongoDB ObjectId, generated on insert                                    |
| `type`            | string           | Source type. Currently the only valid value is `"google_doc"`            |
| `language`        | string           | Target language for vocabulary extraction (e.g. `"danish"`)              |
| `name`            | string           | A human-readable label for this source (chosen by the user)              |
| `resourceId`      | string           | The identifier required to locate and retrieve this source's content. Format is source-type specific — see [Source Type Implementations](#source-type-implementations). |
| `userId`          | string           | The authenticated user who registered this source                        |
| `createdAt`       | string           | ISO 8601 timestamp of when the source was registered                     |
| `lastExtractedAt` | string or `null` | ISO 8601 timestamp of the last successful extraction. `null` if never run |

---

## MongoDB Configuration

To connect to MongoDB, the service configuration must override `get_mongo_secret_names()` and return the secret names for the service's dedicated credentials:

| Config key        | Secret name                        |
|-------------------|------------------------------------|
| `user_secret_name` | `"tome-ms-sources-mongo-user"`    |
| `pwd_secret_name`  | `"tome-ms-sources-mongo-pswd"`    |

The database name used at query time is **`tomesources`**.

---

## API Endpoints

All paths are relative to the service base path `/tomesources`.

| Operation        | Method | Path                             | Delegate           |
|------------------|--------|----------------------------------|--------------------|
| PostSource       | `POST` | `/sources`                       | `PostSource`       |
| GetSources       | `GET`  | `/sources`                       | `GetSources`       |
| ExtractKnowledge | `POST` | `/sources/{sourceId}/extract`    | `ExtractKnowledge` |

---

## Endpoint Specifications

### POST `/sources` — PostSource

Registers a new Data Source. The document content is **not** fetched at this point.

#### Request Body

```json
{
  "type": "google_doc",
  "language": "danish",
  "name": "Week 3 Homework",
  "resourceId": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
}
```

| Field        | Required | Description                                                                           |
|--------------|----------|---------------------------------------------------------------------------------------|
| `type`       | Yes      | Source type. Currently only `"google_doc"` is supported                               |
| `language`   | Yes      | Target language (must be in the supported list)                                       |
| `name`       | Yes      | Human-readable label (non-empty string)                                               |
| `resourceId` | Yes      | The identifier for the resource within its source system. Format is source-type specific — see [Source Type Implementations](#source-type-implementations). |

The `userId` is derived from the authenticated request context (JWT) — it is not accepted from the request body.

Registering the same `(userId, type, resourceId, language)` combination more than once is allowed. Duplicate registrations are the user's responsibility.

#### Response — `201 Created`

```json
{
  "id": "664abc123def456789abcdef"
}
```

#### Error Cases

| Condition                  | Status | Description                              |
|----------------------------|--------|------------------------------------------|
| Missing any required field | `400`  | Required fields not provided             |
| Unsupported `type`         | `400`  | Type is not in the supported list        |
| Unsupported `language`     | `400`  | Language not in the supported list       |
| Invalid `resourceId` format | `400` | Format does not match the rules for the given `type` — see [Source Type Implementations](#source-type-implementations). |

---

### GET `/sources` — GetSources

Returns all Data Sources registered by the authenticated user. The user is identified from the JWT.

#### Query Parameters

| Parameter  | Required | Description                                                                          |
|------------|----------|--------------------------------------------------------------------------------------|
| `language` | No       | Filter by target language (e.g. `"danish"`). An unsupported value returns an empty list, not a `400`. |

#### Response — `200 OK`

```json
{
  "sources": [
    {
      "id": "664abc123def456789abcdef",
      "type": "google_doc",
      "language": "danish",
      "name": "Week 3 Homework",
      "resourceId": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
      "createdAt": "2026-04-01T10:00:00.000Z",
      "lastExtractedAt": null
    }
  ]
}
```

> **`userId` is not included in the response.** It is an internal field used for ownership filtering and is never returned to the client.

---

### POST `/sources/{sourceId}/extract` — ExtractKnowledge

Triggers knowledge extraction for a registered Data Source. This is the main feature of this spec and is described in detail in the [Extraction Workflow](#extraction-workflow) section below.

#### Path Parameters

| Parameter  | Description                                         |
|------------|-----------------------------------------------------|
| `sourceId` | MongoDB ObjectId of the Data Source to process      |

#### Request Body

The request body is empty. All parameters are derived from the stored source document.

#### Response — `200 OK`

Returns a summary of the extraction:

```json
{
  "sourceId": "664abc123def456789abcdef",
  "wordsExtracted": 42,
  "wordsCreated": 38,
  "wordsErrored": 4,
  "sentencesExtracted": 12,
  "sentencesCreated": 11,
  "sentencesErrored": 1
}
```

| Field                | Description                                                                                                                                     |
|----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| `wordsExtracted`     | Number of valid word pairs submitted to `tome-ms-language` after LLM output parsing and local validation (pairs with missing fields are not counted) |
| `wordsCreated`       | Words reported as `"created"` by `tome-ms-language` in the `207` response                                                                      |
| `wordsErrored`       | Words reported as `"error"` by `tome-ms-language` in the `207` response                                                                        |
| `sentencesExtracted` | Number of valid sentence pairs submitted to `tome-ms-language` after LLM output parsing and local validation                                    |
| `sentencesCreated`   | Sentences reported as `"created"` by `tome-ms-language` in the `207` response                                                                  |
| `sentencesErrored`   | Sentences reported as `"error"` by `tome-ms-language` in the `207` response                                                                    |

`wordsCreated + wordsErrored` must always equal `wordsExtracted`. `sentencesCreated + sentencesErrored` must always equal `sentencesExtracted`.

#### Error Cases

| Condition                          | Status | Description                                                      |
|------------------------------------|--------|------------------------------------------------------------------|
| `sourceId` is not a valid ObjectId | `400`  | Malformed ID format                                              |
| `sourceId` not found or not owned  | `404`  | No source with that ID exists for the authenticated user         |
| Source content not accessible      | `502`  | The service cannot read the resource (e.g. permission denied)    |
| LLM consistently fails             | `502`  | LangChain chain fails after retry (see workflow for retry policy)|
| `tome-ms-language` non-207 response | `502` | Downstream vocabulary service returned an unexpected status code |
| `tome-ms-language` unreachable     | `502`  | The downstream vocabulary service is unreachable                 |
| LLM returns zero valid words       | `200`  | Normal response; all count fields will be `0`                    |
| Source content is empty            | `200`  | No text to process; all count fields will be `0`                 |

---

## Extraction Workflow

The `ExtractKnowledge` delegate executes the following steps in order.

### Step 1 — Load the Data Source

Load the source document from the `sources` collection using `sourceId`. Verify:
- The document exists.
- The `userId` on the document matches the authenticated user (ownership check).

If either check fails, return `404`.

### Step 2 — Fetch Source Content

This step dispatches to a **Source Content Fetcher** selected by the source's `type` field. Each source type has its own fetcher; see [Source Type Implementations](#source-type-implementations) for the type-specific behaviour.

**Contract that every fetcher must satisfy:**
- It receives the full source document (all stored fields, including `resourceId`).
- It returns a single **plain-text string** representing the full textual content of the source.
- If the resource cannot be accessed (permission denied, not found, network error), it raises an error that causes `ExtractKnowledge` to return `502`.

**Once the fetcher returns:**
- If the plain-text string is empty, skip Steps 3–5 and return `200` with all counts at `0`.

> **Content length limit:** Plain-text content exceeding **500,000 characters** is rejected with `400` — the source is considered too large to process regardless of type.

> **Chunking strategy:** Content exceeding **100,000 characters** must be split before being passed to the LLM (Step 3). The document is divided into chunks of approximately **3,000 tokens** with an overlap of **200 tokens** between consecutive chunks. All chunk results are merged; duplicate `(english, translation)` pairs (case-insensitive on both fields) appearing across chunks are deduplicated before being submitted to `tome-ms-language`.

### Step 3 — LLM Vocabulary Extraction (LangChain)

Pass the plain-text content (or each chunk) to a LangChain chain configured with the following behaviour:

**Goal:** identify every word or short phrase in the document that is written in the target language (e.g. Danish), along with its English equivalent, and return them as a structured list.

**Expected LLM output (structured / JSON mode):**

```json
{
  "words": [
    { "english": "dog",  "translation": "hund" },
    { "english": "cat",  "translation": "kat"  }
  ]
}
```

**Validation of LLM output:** each entry must have both `english` and `translation` as non-empty strings. Entries that fail this check are silently dropped before the downstream call.

**LLM failure handling:**
- If the LLM returns malformed or unparseable JSON for a given chunk, the implementation must **retry that chunk once** with the same prompt.
- If the retry also fails, the chunk is skipped (its words are treated as `0` extracted) and processing continues with the remaining chunks.
- If **all chunks** fail after their retries, return `502`.
- LLM provider errors (timeout, rate limit, quota exceeded) are treated the same as parse failures for the purpose of this retry policy.

**LLM configuration:**
- The model and provider (e.g. OpenAI, Anthropic, Bedrock) are defined in the service configuration. The LLM API key must be loaded from the secrets manager.
- The prompt must be treated as a service-level concern and must be easy to tune without code changes (e.g. stored in the service configuration or a dedicated prompt file).

### Step 4 — LLM Sentence Extraction (LangChain)

Pass the same plain-text content (or each chunk) to a **separate** LangChain agent dedicated to sentence extraction. This agent runs independently from the vocabulary extraction agent (Step 3) — they may run sequentially or in parallel; the implementation may choose.

**Goal:** identify every complete **sentence or phrase** written in the target language (e.g. Danish) that appears in the source material, along with its English translation. The agent must **only extract sentences already present in the text** — it must never invent or synthesise new sentences.

**Translation priority:**
1. If a translation for the sentence is present in the source material (directly paired with the sentence), use that translation.
2. If no translation is present in the material, generate the English translation using the LLM based on the Danish sentence.

**Expected LLM output (structured / JSON mode):**

```json
{
  "sentences": [
    {
      "sentence": "Jeg kan godt lide at læse bøger.",
      "translation": "I like reading books."
    },
    {
      "sentence": "Hvornår kom du til Danmark?",
      "translation": "When did you come to Denmark?"
    }
  ]
}
```

**Validation of LLM output:** each entry must have both `sentence` and `translation` as non-empty strings. Entries that fail this check are silently dropped.

**LLM failure handling:** applies the same retry policy as Step 3 — one retry per failing chunk, skip the chunk on second failure, return `502` only if all chunks fail.

**LLM configuration:** same rules as Step 3 — model and prompt are service-level concerns, easy to tune without code changes. The sentence extraction prompt must be stored in a **separate prompt file** from the vocabulary extraction prompt.

**Deduplication:** duplicate `(sentence, translation)` pairs appearing across chunks are deduplicated (case-insensitive on `sentence`) before being submitted to `tome-ms-language`.

### Step 5 — Post Vocabulary to tome-ms-language

Call `POST /tomelang/vocabulary/{language}/words/batch` on `tome-ms-language` with the extracted words:

```json
{
  "words": [
    { "english": "dog",  "translation": "hund" },
    { "english": "cat",  "translation": "kat"  }
  ]
}
```

The `language` value is read from the stored Data Source document (e.g. `"danish"`).

**Authentication:** the outbound request must include the user's JWT forwarded from the incoming request, in the standard `Authorization: Bearer <token>` header.

**Correlation:** the outbound request must include the correlation ID from the current execution context in an `x-correlation-id` header, for end-to-end traceability.

If `tome-ms-language` returns any status other than `207`, the extraction fails with `502`. The response body from `tome-ms-language` (if available) should be included in the `502` error detail for debugging.

The `207 Multi-Status` response contains per-word `status` values (`"created"` or `"error"`). These are counted to populate `wordsCreated` and `wordsErrored` in the response.

> **Note on duplicates:** `tome-ms-language` allows multiple translations of the same English word. Deduplication of vocabulary entries across extraction runs is **out of scope** for this service; the vocabulary service is the owner of that concern.

### Step 6 — Post Sentences to tome-ms-language

Call `POST /tomelang/sentences/{language}/batch` on `tome-ms-language` with the extracted sentences:

```json
{
  "sentences": [
    {
      "sentence": "Jeg kan godt lide at læse bøger.",
      "translation": "I like reading books.",
      "knowledgeSource": "664abc123def456789abcdef"
    }
  ]
}
```

The `knowledgeSource` field must be set to the `sourceId` of the Data Source being extracted.

**Authentication and Correlation:** same rules as Step 5 — forward the user's JWT and include the correlation ID.

If `tome-ms-language` returns any status other than `207`, the sentence submission fails. **This does not abort the overall extraction** — a sentence submission failure is logged and the `sentencesErrored` count reflects the failure, but the extraction response is still `200`. The vocabulary counts already computed in Step 5 are unaffected.

The `207 Multi-Status` response contains per-sentence `status` values (`"created"` or `"error"`). These are counted to populate `sentencesCreated` and `sentencesErrored` in the response.

### Step 7 — Update the Data Source Record

Update `lastExtractedAt` on the source document to the current UTC time (ISO 8601). This update happens whenever the extraction workflow reaches this step — regardless of how many words were extracted or how many errored in `tome-ms-language`. The timestamp reflects "extraction was attempted and the workflow completed", not "all words were created successfully".

---

## Source Type Implementations

Each supported source type must provide:
1. A **`resourceId` format** — what value the client must supply when registering a source of this type, and how to validate it.
2. A **Content Fetcher** — the logic that takes a stored source document and returns a plain-text string (Step 2 of the extraction workflow).

When a new source type is added, a new subsection must be created here alongside any type-specific validation wired into `PostSource`.

---

### `google_doc`

#### `resourceId` Format

The `resourceId` must be the **Google Doc document ID**: the alphanumeric string found in the document's URL.

```
https://docs.google.com/document/d/{documentId}/edit
```

The client must extract only the `{documentId}` segment — not the full URL.

**Validation at `PostSource`:** if the supplied `resourceId` contains a `/` character, reject with `400`. A slash reliably indicates a full URL was submitted instead of the bare ID.

#### Content Fetcher

The fetcher uses the **GCP Service Account** credentials available to the service. The user must share the document with the service account before extraction can succeed.

1. Call the Google Docs API `documents.get` endpoint using the `resourceId` as the document ID.
2. Traverse **all structural elements** in the document body and extract their text content: paragraphs, tables (every cell), lists, and headers. Content in footnotes and comments is excluded.
3. Concatenate the extracted text with newline separators between structural units to produce the output plain-text string.

**Error handling:**
- A permission error from the Google Docs API must surface as a `502` with a message instructing the user to share the document with the service account.
- Any other API error (not found, quota exceeded, network failure) also surfaces as `502`.

---

## Integration — tome-ms-language

The `tome-ms-language` base URL must be provided via an environment variable or secret (e.g. `TOME_LANGUAGE_URL`). The service calls the following endpoints:

| Method | Path                                             | Purpose                   |
|--------|--------------------------------------------------|---------------------------|
| `POST` | `/tomelang/vocabulary/{language}/words/batch`    | Bulk-insert vocabulary    |
| `POST` | `/tomelang/sentences/{language}/batch`           | Bulk-insert sentences     |
| `GET`  | `/tomelang/vocabulary/{language}/words/sample`   | Random word sample (used by sentence generation — see [`sentence-generation.md`](./sentence-generation.md)) |

**Authentication:** Forward the user's JWT from the incoming request as `Authorization: Bearer <token>`.

**Traceability:** Include the execution context's correlation ID as `x-correlation-id`.

---

## Business Rules

1. **Supported source types:** The list of supported types is defined in service configuration. Currently only `"google_doc"` is implemented. Adding a new type requires adding a Content Fetcher and a subsection in [Source Type Implementations](#source-type-implementations), with no changes to the core workflow.
2. **Supported languages:** Matches the supported list in `tome-ms-language`. Currently `"danish"` only. The list must be centralised in service configuration so adding a language requires no code changes.
3. **Ownership:** A user can only list and trigger extraction on their own sources. Attempting to extract a source owned by another user returns `404` (not `403`), to avoid leaking the existence of other users' sources.
4. **Repeated extraction:** Calling `ExtractKnowledge` multiple times on the same source is allowed. Each run reprocesses the current document and pushes whatever the LLM extracts. Because `tome-ms-language` permits duplicate vocabulary entries, this will create duplicates. This is by design.
5. **Duplicate sources:** A user may register the same `resourceId` more than once (e.g. for different languages, or by mistake). No uniqueness constraint is enforced at registration time.
6. **Extraction is synchronous:** The extraction endpoint waits for the full workflow to complete before responding. The maximum document size limit (500,000 characters) is the primary guard against runaway processing time.

---

## Out of Scope

- Pagination of `GetSources` results.
- Support for source types beyond `"google_doc"` (PDFs, Word docs, websites, etc.) — the architecture is designed to accommodate them via the Source Type Implementations pattern, but they are not implemented in this spec.
- Scheduled / automatic extraction (extraction is always user-triggered).
- Vocabulary deduplication across extraction runs.
- Deletion of Data Sources.
- Soft deletes.
- Progress streaming for long-running extractions.
- Per-source extraction history or audit log.
- Async / background job processing (extraction is synchronous).
