# Sentence Generation — Feature Spec

## Overview

This spec defines the on-demand **sentence generation** capability in `tome-ms-sources`.

While [Source Knowledge Extraction](./source-knowledge-extraction.md) extracts sentences that are already present in user-provided source material, sentence generation creates **new sentences** using an LLM agent. The agent uses existing vocabulary words from `tome-ms-language` as seed material, generates fluent Danish sentences that use those words, and stores them back in `tome-ms-language`.

Generated sentences are distinguished from extracted sentences by the `knowledgeSource` value `"tome-agent"`.

---

## API Endpoint

### POST `/sentences/generate` — GenerateSentences

Triggers on-demand sentence generation.

#### Request Body

```json
{
  "language": "danish",
  "count": 10
}
```

| Field      | Required | Description                                                                        |
|------------|----------|------------------------------------------------------------------------------------|
| `language` | Yes      | Target language (e.g. `"danish"`). Must be in the supported language list.         |
| `count`    | Yes      | Number of sentences to generate (`Ns`). Must be a positive integer. Maximum: `50`. |

#### Response — `200 OK`

```json
{
  "language": "danish",
  "sentencesGenerated": 10,
  "sentencesCreated": 9,
  "sentencesErrored": 1
}
```

| Field                | Description                                                                             |
|----------------------|-----------------------------------------------------------------------------------------|
| `sentencesGenerated` | Number of valid sentences produced by the generation agent (after the verification pass) |
| `sentencesCreated`   | Sentences reported as `"created"` by `tome-ms-language` in the `207` response           |
| `sentencesErrored`   | Sentences reported as `"error"` by `tome-ms-language` in the `207` response             |

#### Error Cases

| Condition                          | Status | Description                                              |
|------------------------------------|--------|----------------------------------------------------------|
| Missing `language` or `count`      | `400`  | Required fields not provided                             |
| Unsupported `language`             | `400`  | Language is not in the supported list                    |
| `count` ≤ 0 or > 50               | `400`  | Count is out of the allowed range                        |
| No vocabulary words available      | `200`  | Vocabulary is empty; all counts will be `0`              |
| LLM generation agent fails         | `502`  | LLM agent fails after retry                              |
| LLM verification agent fails       | `502`  | Verification agent fails after retry                     |
| `tome-ms-language` unreachable     | `502`  | The downstream service is unreachable                    |

---

## Generation Workflow

### Step 1 — Sample Vocabulary Words

Call `GET /tomelang/vocabulary/{language}/words/sample?n=M` on `tome-ms-language` to retrieve a random set of `M` vocabulary words.

`M` is a service-level configuration value (default: `30`). It is not exposed in the request body — the caller only specifies how many sentences to generate (`count`), not how many words to seed the generator with.

If the vocabulary is empty (the endpoint returns an empty list), skip Steps 2–4 and return `200` with all counts at `0`.

### Step 2 — LLM Sentence Generation Agent

Pass the sampled vocabulary words to a **dedicated sentence generation LangChain agent**. This agent is distinct from both the vocabulary extraction agent and the sentence extraction agent — it has its own prompt file.

**Goal:** generate exactly `count` sentences in the target language (e.g. Danish). Each sentence must:
- Be grammatically correct Danish.
- Naturally use at least one of the sampled vocabulary words.
- Have an English translation.
- Be realistic, complete sentences — not single words or fragments.

**Expected LLM output (structured / JSON mode):**

```json
{
  "sentences": [
    {
      "sentence": "Jeg kan godt lide at læse bøger om dansk kultur.",
      "translation": "I like reading books about Danish culture."
    },
    {
      "sentence": "Hun vænner sig langsomt til det kolde vejr.",
      "translation": "She is slowly getting used to the cold weather."
    }
  ]
}
```

**Validation:** each entry must have both `sentence` and `translation` as non-empty strings. Entries that fail this check are silently dropped.

**LLM failure handling:** one retry on failure; return `502` if the retry also fails.

### Step 3 — Danish Language Expert Verification Agent

Pass all generated sentences from Step 2 through a **second LLM agent** that acts as a Danish language expert. This agent's sole purpose is to verify grammatical and linguistic correctness. It reviews each sentence and returns only the sentences it considers correct Danish.

**Goal:** filter out any sentences that are grammatically wrong, unnatural, or implausible in Danish. The agent should not rewrite sentences — it either accepts or rejects each one as-is.

**Expected LLM output (structured / JSON mode):**

```json
{
  "sentences": [
    {
      "sentence": "Jeg kan godt lide at læse bøger om dansk kultur.",
      "translation": "I like reading books about Danish culture."
    }
  ]
}
```

The verified set may be smaller than the input set if some sentences were rejected.

**LLM failure handling:** one retry on failure; return `502` if the retry also fails.

> **Note:** If the verified set is empty (all sentences rejected), return `200` with all counts at `0`. This is a valid outcome, not an error.

### Step 4 — Post Sentences to tome-ms-language

Call `POST /tomelang/sentences/{language}/batch` on `tome-ms-language` with the verified sentences:

```json
{
  "sentences": [
    {
      "sentence": "Jeg kan godt lide at læse bøger om dansk kultur.",
      "translation": "I like reading books about Danish culture.",
      "knowledgeSource": "tome-agent"
    }
  ]
}
```

The `knowledgeSource` field must always be `"tome-agent"` for generated sentences.

**Authentication and Correlation:** forward the user's JWT and include the correlation ID, same as the extraction workflow.

If `tome-ms-language` returns any status other than `207`, the request fails with `502`.

---

## LLM Configuration

- The sentence generation agent and the verification agent each use their own **separate prompt files**. Prompts must be easy to tune without code changes.
- The model and provider are defined in the service configuration (same pattern as the extraction agents).
- The number of seed words `M` must be a service-level configuration value (not hardcoded).

---

## Integration — tome-ms-language

The following endpoints are used:

| Method | Path                                             | Purpose                        |
|--------|--------------------------------------------------|--------------------------------|
| `GET`  | `/tomelang/vocabulary/{language}/words/sample`   | Fetch random seed vocabulary   |
| `POST` | `/tomelang/sentences/{language}/batch`           | Store generated sentences      |

**Authentication:** Forward the user's JWT from the incoming request as `Authorization: Bearer <token>`.

**Traceability:** Include the execution context's correlation ID as `x-correlation-id`.

---

## Business Rules

1. **`count` cap:** A maximum of `50` sentences may be generated per request to limit LLM latency and cost.
2. **Seed words:** The number of words sampled from vocabulary (`M`) is a server-side setting, decoupled from `count`. Using more seed words generally produces more varied sentences.
3. **No deduplication:** The same sentence may be generated and stored multiple times across calls. Deduplication is out of scope.
4. **Provenance:** All sentences produced by this workflow carry `knowledgeSource = "tome-agent"` so they can be distinguished from sentences extracted from source material.
5. **Verification is mandatory:** The verification step (Step 3) cannot be bypassed. It ensures quality and guards against LLM hallucinations generating incorrect Danish.

---

## Out of Scope

- Scheduling or batch generation (generation is always user-triggered).
- Sentence difficulty classification.
- Targeting specific vocabulary words (the seed sample is random).
- Re-generating or updating previously generated sentences.
- Progress streaming for long-running generation.
