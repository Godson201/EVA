# EVA V2 Translation

Phase 6 provides English–Kinyarwanda translation through `POST /api/v1/translations` and keeps a compatibility request at `POST /api/translate`.

Supported modes:

- `direct`: NLLB translation without stylistic rewriting
- `natural`: idiomatic output
- `simple`: simpler vocabulary and sentences
- `professional`: polished workplace language
- `academic`: precise academic language
- `call-center`: concise, courteous spoken customer-service language

NLLB is loaded lazily on the first translation request and retained once per process. Inference runs outside the FastAPI event loop and is serialized because the tokenizer's source-language state is mutable. The implementation uses the official NLLB `eng_Latn` and `kin_Latn` language codes.

Non-direct modes use the configured LLM provider for style-aware translation. If it is unavailable, EVA falls back to NLLB and reports `fallback_used: true` rather than losing translation functionality.

If `source_language` is omitted, EVA applies a conservative English/Kinyarwanda detector. Detection confidence is intentionally not presented as certainty; clients should allow a user override when the result is wrong or the input is too short.

Translations are stored with the owner, original text, output, language pair, mode, provider, and optional conversation UUID. Listing is owner-scoped.
