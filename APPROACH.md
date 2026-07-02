# Approach

## Design Choices

I built a FastAPI service over the official SHL Individual Test Solutions catalog. The API is stateless: `/chat` receives the full conversation history and reconstructs context on each request. Gemini is used only for intent extraction when `GEMINI_API_KEY` is configured; final assessment selection remains retrieval-driven and catalog-validated so the service cannot return invented products or URLs.

The catalog JSON is the primary source. The provided file contains one invalid control character in a product name, so `scripts/process_catalog.py` uses Python's tolerant JSON decoder and normalizes that official-file formatting issue into `Microsoft Excel 365 (New)` based on the product URL. The processed catalog keeps names, URLs, descriptions, job levels, languages, duration, remote/adaptive fields, and SHL test-type keys. Test-type labels are mapped deterministically to API codes such as `K`, `P`, `A`, `S`, `B`, `C`, and `D`.

## Retrieval Setup

The recommender uses scikit-learn `TfidfVectorizer` with word and bigram features over each catalog entry's name, description, keys, job levels, languages, duration, and URL. Gemini first summarizes messy conversation or job-description text into compact search intent. Ranking then combines cosine similarity with deterministic rule boosts for seniority, skill terms, personality/cognitive/situational intent, duration constraints, simulations, and adaptive testing. If Gemini is unavailable or slow, the same retrieval layer runs on the raw conversation text.

The public sample conversations showed that pure keyword retrieval misses expected batteries for common scenarios. I added a small catalog-grounded intent layer for high-signal patterns such as Java/Spring/SQL, contact center language screens, graduate scenarios, sales reskilling, healthcare/HIPAA, safety/dependability, finance graduates, and senior leadership. Those rules only select product names that exist in the local catalog; final recommendations are validated against loaded catalog entries before returning.

## Agent Behavior And Prompt Design

The agent asks one clarification question only when the request is too vague or when a key catalog constraint matters, such as spoken-language market for contact-center SVAR or Spanish/English tradeoffs for HIPAA knowledge tests. Once there is enough role or skill context, it recommends immediately to respect the 8-turn evaluation cap.

Gemini's prompt is intentionally narrow: it must return one compact intent line and must not recommend products, invent catalog names, or include URLs. Refinement is handled by reading the previous assistant reply from the supplied conversation history, extracting catalog product names, and applying additions/removals from the latest user turn. Comparisons are answered with catalog descriptions, keys, and duration only, with no recommendation shortlist. Safety checks refuse prompt injection, legal advice, general hiring advice, off-topic questions, and non-SHL requests.

The LLM is never trusted as a source of catalog truth. It improves intent extraction; the local catalog layer still generates and validates the recommendation list.

## Evaluation Approach

I used the PDF requirements and the ten public sample conversations to identify core behaviors and expected shortlist patterns. Automated tests cover `/health`, schema stability, invalid request handling, vague-query clarification, Java developer retrieval, pasted job descriptions, refinement, comparison, legal/off-topic/prompt-injection refusal, statelessness, LLM fallback, LLM intent augmentation, and catalog-only URL validation.

What did not work: strict JSON parsing failed on the official catalog due to an invalid control character; tolerant decoding fixed this without inventing data. Pure TF-IDF also over-ranked adjacent technical tests for explicit batteries, so I measured improvement by checking sample-like prompts and changed the system to use Gemini intent extraction plus explicit catalog-grounded intent matches when at least three strong products are found.

AI tools used: Codex was used to inspect the assignment, implement the FastAPI project, generate tests and documentation, and run local verification. Gemini is used at runtime for intent extraction only; recommendation grounding remains deterministic and auditable.
