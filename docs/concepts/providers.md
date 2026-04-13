# Providers

FixtureForge is provider-agnostic. It auto-detects your provider from environment variables and falls back gracefully when no key is set.

---

## Auto-Detection Order

```
ANTHROPIC_API_KEY  ->  Claude  (claude-haiku-4-5-20251001)
OPENAI_API_KEY     ->  GPT     (gpt-4o-mini)
GOOGLE_API_KEY     ->  Gemini  (gemini-2.0-flash)
GROQ_API_KEY       ->  Groq    (llama-3.3-70b-versatile)
(none found)       ->  Ollama  (localhost:11434)
(Ollama down)      ->  Deterministic-only (no AI)
```

---

## Explicit Configuration

```python
# Anthropic Claude
forge = Forge(provider_name="anthropic", model="claude-sonnet-4-6")

# OpenAI
forge = Forge(provider_name="openai", model="gpt-4o")

# Groq
forge = Forge(provider_name="groq", model="llama-3.3-70b-versatile")

# Local Ollama
forge = Forge(provider_name="ollama", model="llama3.2")

# No AI
forge = Forge(use_ai=False)
```

---

## Recommended: Groq Free Tier

Groq offers a generous free tier that works well for development:

- **14,400 requests/day** on `llama-3.3-70b-versatile`
- Fast inference (~300 tokens/sec)
- No credit card required

```bash
pip install "fixtureforge[groq]"
export GROQ_API_KEY=gsk_...
```

```python
forge = Forge()  # auto-detects Groq from GROQ_API_KEY
```

---

## Response Cache

AI responses are cached locally for **7 days**. Identical requests cost nothing after the first call.

```python
forge = Forge(use_cache=True)   # default — cache at ~/.fixtureforge/cache/
forge = Forge(use_cache=False)  # disable caching
```

This means running your test suite twice with the same models and contexts costs half as many API calls.

---

## Cost Optimization

FixtureForge uses several strategies to minimize API costs:

| Strategy | Saving |
|----------|--------|
| Field routing (only semantic fields hit AI) | ~70-90% |
| Batch prompting (all records in one call) | ~95% latency |
| Response cache (7-day TTL) | 100% on repeat runs |
| SYSTEM_PROMPT_DYNAMIC_BOUNDARY (static prompt cached once) | ~40% |
| DataSwarms shared cache | ~90% per additional model |
