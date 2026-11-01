# ADR-007: Groq GPT-OSS 120B for answer generation

- **Status:** Accepted for implementation; live provider verification pending
- **Date:** 2026-11-01

## Context

The RAG query pipeline needs a dedicated answer-generation model that turns retrieved IIIT Bhagalpur evidence into concise answers and cites backend-issued evidence IDs. The scanned-PDF transcription path already uses Groq-hosted Qwen 3.8 27B for image input, but OCR and final answer generation are separate responsibilities.

## Decision

Use OpenAI GPT-OSS 120B hosted by Groq with model ID `openai/gpt-oss-120b` through Groq's OpenAI-compatible Chat Completions API at `https://api.groq.com/openai/v1`.

Use `GROQ_API_KEY` for both the Qwen VLM and GPT-OSS answer model by default. `ANSWER_MODEL_API_KEY` may override it when a separate Groq key is intentionally configured. Keep provider and model selection in backend environment settings; never expose credentials to the frontend.

## Alternatives considered

- Groq-hosted GPT-OSS 20B: lower-cost and faster, but the 120B model is selected as the stronger default for institutional question answering.
- OpenRouter: not selected.
- Groq Qwen VLM as the answer model: rejected because the VLM's primary role is scanned-page image transcription, not final RAG response generation.

## Consequences

- The existing OpenAI-compatible adapter can be reused without adding another SDK dependency.
- Answer generation is enabled once `GROQ_API_KEY` is populated in `backend/.env`.
- The API process must be restarted after changing `.env` so cached settings are reloaded.
- Live provider compatibility, response shape, citation adherence, latency and rate limits must be verified with a controlled smoke test before bulk indexing or production use.
- Retrieved document content remains untrusted. The backend continues to validate all returned citation IDs against the retrieved evidence set.

## References

- [Groq supported models](https://console.groq.com/docs/models)
- [Groq GPT-OSS built-in tools and model guidance](https://console.groq.com/docs/tool-use/built-in-tools)
