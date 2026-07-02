# SHL Assessment Recommender

Conversational FastAPI service for recommending SHL assessments from the official SHL Individual Test Solutions catalog. The service is stateless: every `/chat` request includes the full conversation history, and recommendations are always validated against the local catalog.

## What It Does

- Clarifies vague assessment requests before recommending.
- Recommends 1 to 10 SHL catalog assessments when enough context is present.
- Handles job descriptions, refinements, confirmations, and assessment comparisons.
- Refuses legal advice, general hiring advice, prompt injection, unrelated topics, and non-SHL recommendations.
- Uses Gemini for intent extraction when `GEMINI_API_KEY` is set.
- Uses catalog retrieval for final selection: local JSON catalog + TF-IDF cosine similarity + rule boosts.
- Validates every returned recommendation against the local SHL catalog.

## Project Structure

```text
app/
  agent.py        # stateless conversation and refinement logic
  catalog.py      # catalog loading, validation, test-type mapping
  config.py       # paths and constants
  main.py         # FastAPI endpoints
  llm.py          # optional Gemini intent extraction
  retrieval.py    # TF-IDF retrieval and deterministic ranking
  safety.py       # scope/refusal checks
  schemas.py      # Pydantic API models
data/
  catalog_raw.json
  catalog_processed.json
  sample_conversations.zip
scripts/
  download_resources.py
  process_catalog.py
tests/
  test_*.py
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Setup

The official catalog and sample conversations are already included in `data/`. To refresh them:

```bash
python scripts/download_resources.py
python scripts/process_catalog.py
```

Gemini is optional locally but should be configured in deployment if you want the submitted API to use an LLM:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export GEMINI_MODEL="gemini-3.5-flash"
```

If Gemini is unavailable, slow, or not configured, the service falls back to deterministic catalog retrieval.

## Run Locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Chat example:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hiring a senior Java engineer with Spring, SQL, AWS and Docker"}]}'
```

Response shape:

```json
{
  "reply": "Here is a grounded SHL shortlist from the catalog: ...",
  "recommendations": [
    {
      "name": "Core Java (Advanced Level) (New)",
      "url": "https://www.shl.com/products/product-catalog/view/core-java-advanced-level-new/",
      "test_type": "K"
    }
  ],
  "end_of_conversation": false
}
```

## Test

```bash
pytest
```

The tests cover health, response schema, invalid request handling, vague-query clarification, Java and job-description recommendations, refinement, comparison, refusal behavior, statelessness, retrieval, and catalog-only URL validation.

## Deploy

### Render

1. Push this folder to a Git repository.
2. Create a Render Web Service.
3. Use Python 3.11.
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables:
   - `PYTHON_VERSION=3.11.11`
   - `GEMINI_API_KEY=<your Gemini API key>`
   - `GEMINI_MODEL=gemini-3.5-flash`
7. Verify `/health` and `/chat` after deployment.

### Docker

```bash
docker build -t shl-assessment-recommender .
docker run -p 8000:8000 shl-assessment-recommender
```

## Requirement Checklist

- `GET /health` returns `{"status":"ok"}`.
- `POST /chat` returns exactly `reply`, `recommendations`, and `end_of_conversation`.
- Stateless conversation handling.
- 1 to 10 recommendations only when making a shortlist.
- Empty recommendations for clarifications and refusals.
- All returned names and URLs are from `data/catalog_processed.json`.
- Uses Gemini only for intent extraction; no LLM output is trusted as a catalog recommendation.
- Uses SHL catalog data only; no fabricated assessments or URLs.
- Supports clarification, recommendation, refinement, comparison, and refusal.
- Includes tests, Dockerfile, and Render-compatible setup.

## Known Limitations

- If Gemini is missing or times out, the service falls back to deterministic retrieval.
- If the catalog lacks a direct skill test, it recommends the closest catalog-grounded alternatives and says so.
- Comparisons are limited to catalog fields available in the official JSON.

## Submission

Submit the deployed public API endpoint URL and `APPROACH.md` through the SHL form from the assignment PDF. Keep the service reachable at submission time.
