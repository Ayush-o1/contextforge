# ContextForge — Interview & Viva Preparation Plan

> **Internal document.** This is a personal study guide created during development. It is not part of the official project documentation. For architecture reference, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

> Optimized for: Resume discussions · Technical interviews · Project viva · System design rounds

---

## Tier 1 — Must Master Deeply

These are the sub-phases where you must be able to explain every design decision, every tradeoff, and every line of code without looking. These are what make the project impressive on a resume.

---

### 3.3 — Semantic Cache Orchestrator (`cache.py`)

**Why Tier 1:**
This is the core novel feature of the project. No interviewer will skip it. It's what separates ContextForge from "just another proxy."

**Level of understanding required:**
- Explain the two-layer architecture (FAISS for similarity, Redis for storage) and *why* two layers are needed
- Walk through `lookup()` step by step — embed → search → threshold → Redis fetch
- Walk through `store()` — hash → embed → Redis set (with TTL) → FAISS add
- Explain what happens when Redis TTL expires but FAISS still has the vector (stale vector problem)
- Explain `invalidate()` and `flush()` and when you'd use each
- Explain what `CacheResult` carries and why `similarity_score` is always returned even on miss

**Interview questions to expect:**
- "Why store vectors in FAISS and responses in Redis? Why not one system?"
- "What is a semantic cache miss? How is it different from a normal cache miss?"
- "What happens if Redis and FAISS are out of sync?"
- "How does TTL work in a two-layer store? What's your eviction strategy?"
- "Can your cache return the wrong answer? When?"
- "How would you scale this cache horizontally?"

**Time to spend:** 4–5 hours

---

### 3.2 — FAISS Vector Store (`vector_store.py`)

**Why Tier 1:**
FAISS is the most technically differentiated component. Most candidates can talk about Redis caching; almost none have used FAISS in production. This is your sharpest resume differentiator.

**Level of understanding required:**
- What `IndexFlatIP` means — exact search using inner product (not approximate, not L2)
- Why vectors must be L2-normalized before `IndexFlatIP` to get cosine similarity
- How `add()`, `search(k=1)`, `remove_by_key()` work — especially that FAISS has no native delete, you maintain a parallel key list
- Why the index is in-memory and what that means for restarts (`persist` / `load` via `faiss.write_index`)
- What `dimension` means and why it must match the embedder's output dimension exactly

**Interview questions to expect:**
- "What is FAISS and why did you choose it over a vector database like Pinecone?"
- "What's the difference between exact and approximate nearest neighbor search?"
- "How do you delete a vector from a FAISS index? What's the tradeoff?"
- "What happens to the FAISS index when the server restarts?"
- "Why are you using inner product instead of L2 distance?"
- "How many vectors can this index hold before you'd need to rethink it?"

**Time to spend:** 4–5 hours

---

### 3.7 — Full Pipeline Integration (`main.py` lines 175–265, non-streaming)

**Why Tier 1:**
This is the only place in the codebase where all systems come together. In a viva or system design interview, you'll be asked to trace a request from entry to response. This sub-phase is that trace.

**Level of understanding required:**
- Recite the call order *by heart*: route → compress → threshold → embed → FAISS search → Redis fetch (or forward + store)
- Explain *why* compression happens before cache lookup (compress first, then check if the compressed version is cached)
- Explain *why* routing happens before compression (need the model selected before counting tokens for compression)
- Explain `request.state.*` and how telemetry piggybacks without the route calling telemetry directly
- Explain the `X-Cache`, `X-Model-Tier`, `X-Model-Selected` headers and why they matter for debugging

**Interview questions to expect:**
- "Walk me through what happens when a request hits `/v1/chat/completions`."
- "Why does compression happen before cache lookup and not after?"
- "How does the route know which model to use?"
- "If I call the same prompt twice, what happens the second time?"
- "How does telemetry get recorded without the route explicitly calling it?"
- "What's returned to the client on a cache hit vs. a miss?"

**Time to spend:** 3–4 hours (after all other sub-phases are understood)

---

### 2.2 — LiteLLM Router Init + Fallback Chains (`proxy.py`)

**Why Tier 1:**
Multi-provider failover with zero client-side impact is the second most impressive architectural claim on your resume. You need to be able to defend every design decision here.

**Level of understanding required:**
- Explain the `model_list` structure — what `model_name` vs. `litellm_params.model` are and why they differ
- Explain the fallback chain format: `[{"gpt-4o": ["claude-3-5-sonnet", "gemini-2.5-pro"]}]`
- Explain `routing_strategy="simple-shuffle"` — load balancing across equal-priority deployments
- Explain `num_retries=2` — retries within the same deployment before escalating to fallbacks
- Explain why the model list is built dynamically from available API keys (not hardcoded) and the implications

**Interview questions to expect:**
- "What happens if OpenAI is down? How does your system handle it?"
- "How do you add a new provider to your system?"
- "What's the difference between retry and fallback in your architecture?"
- "How does LiteLLM handle provider-specific API formats?"
- "What's your failover latency? Does it add to response time?"
- "How do you test failover without taking down a real provider?"

**Time to spend:** 3–4 hours

---

## Tier 2 — Should Understand Well

These sub-phases are asked about in project interviews and vivas. You need confident, accurate answers — not line-by-line mastery.

---

### 3.6 — Adaptive Threshold Auto-Tuner (`adaptive.py`)

**Why Tier 2:**
Adaptive systems are architecturally interesting and stand out. But this module is small and fairly self-contained — you don't need to memorize SQLite syntax, just the feedback loop concept.

**Level of understanding required:**
- Explain the control logic: hit_rate > 60% → threshold too permissive → raise it; hit_rate < 20% → too strict → lower it
- Explain why the step size is 0.01 and bounded by `[adaptive_threshold_min, adaptive_threshold_max]`
- Explain how `get_active_threshold()` bridges static config and adaptive value
- Explain when you would call `POST /v1/threshold/evaluate` manually vs. triggering it automatically

**Interview questions to expect:**
- "How does your system improve its cache hit rate over time?"
- "What is the risk of adaptive thresholds being too aggressive?"
- "When would the adaptive threshold help vs. hurt?"
- "What safeguards prevent the threshold from drifting to 1.0 or 0.0?"

**Time to spend:** 2–3 hours

---

### 3.5 — Context Compressor (`compressor.py`)

**Why Tier 2:**
Token/cost reduction is one of the three stated goals of the project. Interviewers will ask about it. But the implementation is straightforward enough that you don't need line-level mastery.

**Level of understanding required:**
- Explain the two gates: token count > threshold AND non-system turns > min_turns
- Explain the split strategy: keep system + recent turns verbatim, summarize only old turns
- Explain why you use a cheap model (`compress_summary_model`) for summarization and not the requested model
- Explain the compression ratio output and how it flows into telemetry headers

**Interview questions to expect:**
- "How does your system handle very long conversations?"
- "Doesn't summarizing the context lose information?"
- "How do you decide how much of the conversation to summarize?"
- "What's the cost of compression itself? Is it always worth it?"

**Time to spend:** 2–3 hours

---

### 2.5 — Failover & Retry Mechanics (`proxy.py`)

**Why Tier 2:**
Resilience engineering is a common senior interview theme. You need to explain the three-layered resilience story (retry → fallback → error) clearly.

**Level of understanding required:**
- Explain `num_retries=2` within a deployment, then the Router escalates to the fallback list
- Explain `UpstreamError` — why you wrap all provider exceptions into one type
- Explain `_map_error()` — extracts `status_code` from provider exceptions (which have different shapes)
- Know the explicit fallback chains: gpt-4o → claude-3-5-sonnet → gemini-2.5-pro

**Interview questions to expect:**
- "What's your error handling strategy when an upstream API fails?"
- "How do you prevent cascading failures?"
- "How do you distinguish a transient error from a hard failure?"
- "What's the maximum number of upstream calls a single request can trigger?"

**Time to spend:** 2–3 hours

---

### 3.4 — Prompt Complexity Classifier & Router (`router.py`)

**Why Tier 2:**
Cost-optimized routing is specifically listed as a core feature. You should be able to explain the classification logic clearly without reading the code.

**Level of understanding required:**
- Explain the classification priority: complex keywords > token count > simple keywords > default COMPLEX
- Explain why COMPLEX is the safe default (underestimating complexity is worse than overestimating)
- Explain YAML-driven config — why rules live in `config/routing_rules.yaml` not hardcoded
- Explain the `override_model` header path and `test_mode`

**Interview questions to expect:**
- "How does your system decide which model to use for a given request?"
- "What stops a simple prompt from being sent to an expensive model?"
- "Why did you choose rule-based classification over ML-based?"
- "How would you extend the router to support a third tier?"

**Time to spend:** 2 hours

---

### 3.1 — Embedding Pipeline (`embedder.py`)

**Why Tier 2:**
The embedder is used everywhere in Phase 3 but is architecturally thin. You need to understand what it does without necessarily knowing `sentence-transformers` internals.

**Level of understanding required:**
- What `messages_to_text()` does and why message role/content are both included
- What `embed(text)` returns (a float32 numpy array of fixed dimension)
- What `content_hash()` does and why it's separate from the semantic vector (exact duplicate detection)
- Why the dimension must match the FAISS index's initialized dimension

**Interview questions to expect:**
- "How do you convert a conversation to a vector?"
- "What embedding model are you using? Why?"
- "What is the dimension of your embeddings? Why does it matter?"

**Time to spend:** 1.5–2 hours

---

### 1.7 — SSE Streaming Route

**Why Tier 2:**
Streaming is a key differentiator vs. batch LLM APIs. You must be able to explain the protocol and why cache/compression are bypassed.

**Level of understanding required:**
- Explain Server-Sent Events: one-way, text-based, `data: {...}\n\n` format
- Explain why streaming bypasses semantic cache (you can't cache a stream you haven't finished receiving)
- Explain `StreamingResponse` + `AsyncGenerator` in FastAPI
- Explain the `X-Accel-Buffering: no` header and what it does

**Interview questions to expect:**
- "Why can't you cache streaming responses?"
- "How does your streaming implementation differ from returning a full response?"
- "What happens if the client disconnects mid-stream?"

**Time to spend:** 2 hours

---

### 1.4 — App Lifespan & Dependency Wiring (`main.py` lifespan)

**Why Tier 2:**
Interviewers ask "how is your app initialized?" In a viva you'll be asked to explain startup and teardown. This is the answer.

**Level of understanding required:**
- Why `@asynccontextmanager` lifespan replaces `@app.on_event` startup/shutdown
- The initialization order and why it matters (Embedder before VectorStore, Redis before SemanticCache)
- What happens on `yield` vs. after `yield` (startup vs. shutdown)
- What `app.state` is and why it's used instead of global variables

**Interview questions to expect:**
- "How do you initialize shared resources in FastAPI?"
- "How do you ensure clean shutdown of Redis connections?"
- "Why not use a global variable for the proxy client?"

**Time to spend:** 1.5–2 hours

---

## Tier 3 — Medium-Level Understanding Is Enough

These sub-phases matter for completeness but are unlikely to be the focus of technical interviews. Know the what and the why — not the how.

---

### 1.1 — Config / Settings | 1.2 — Models

**Why Tier 3:**
Pure boilerplate — Pydantic settings and request models. No one interviews on this. But you need to know what fields exist when asked "what does your request schema look like?"

**What's enough:**
- Know which env vars exist and what they control
- Know the fields of `ChatCompletionRequest` (model, messages, stream, tools, temperature)
- Know what `HealthResponse` returns

**Time to spend:** 45 minutes total

---

### 1.3 — Middleware | 1.5 — Health & Admin Routing

**Why Tier 3:**
Standard FastAPI patterns. Only interesting in the context of "how does telemetry get written? " which you cover under 3.7.

**What's enough:**
- Know that `TelemetryMiddleware` reads `request.state` after the route handler returns
- Know `/health` exists and returns 200
- Know the admin router is separate from the main router

**Time to spend:** 1 hour total

---

### 2.1 — Model Name Resolution

**Why Tier 3:**
Implementation detail. No one asks "how do you convert gpt-4o to openai/gpt-4o?" But you should be able to say "we auto-detect the provider prefix from the model name and API keys available."

**What's enough:**
- Understand the concept: bare name → prefixed name via stem map or API key inference
- Don't need to remember the full `_PREFIX_BY_STEM` dict

**Time to spend:** 30 minutes

---

### 2.3 — Non-Streaming Forward | 2.4 — Streaming Forward

**Why Tier 3:**
These are thin wrappers over LiteLLM Router. The interesting part (failover, model routing) is in 2.2 and 2.5. These methods just call `router.acompletion()`.

**What's enough:**
- Know that `forward()` calls `router.acompletion(stream=False)` and returns a dict
- Know that `forward_stream()` calls `router.acompletion(stream=True)` and yields SSE chunks
- Know `simple_completion()` is a lightweight internal variant for the compressor

**Time to spend:** 1 hour total

---

### 2.6 — Tool Translation Guard

**Why Tier 3:**
Interesting pattern but rarely the focus unless your interviewer specifically asks about tool/function calling support. The important claim is: "LiteLLM auto-translates OpenAI tool format — we just guard against providers that don't support it."

**What's enough:**
- Know which providers are in `_TOOL_UNSUPPORTED_PROVIDERS` (Ollama, HuggingFace, Replicate)
- Know the guard raises 400 before the upstream call, not after

**Time to spend:** 30 minutes

---

### 2.7 — Admin API Endpoints

**Why Tier 3:**
Read-only operational endpoints. Not architecturally interesting. Only relevant if asked "how do you monitor the system?"

**What's enough:**
- Know it exposes cost + request log data from telemetry
- Know it's a separate sub-router, not inline in main.py

**Time to spend:** 20 minutes

---

## Step-by-Step Study Sequence

Do these in order. Each step has a clear completion gate before moving forward.

---

### Step 1 — Set the Foundation
**Sub-phases:** 1.1 → 1.2 → 2.1 → 3.1

**Why grouped:**
All four are pure data/config layers with no async, no business logic, no I/O (except `sentence-transformers` loading). Building blocks for everything else.

**Finish when you can:**
- State every relevant env var in `config.py` from memory
- Draw the fields of `ChatCompletionRequest`
- Explain model name resolution with one example (e.g. `claude-3-5-sonnet → anthropic/claude-3-5-sonnet-20241022`)
- Explain what `embedder.embed()` returns and why dimension matters

---

### Step 2 — The FAISS + Cache Core (your biggest differentiator)
**Sub-phases:** 3.2 → 3.3

**Why grouped:**
`VectorStore` is meaningless without `SemanticCache` to orchestrate it. Study them back-to-back and trace a full lookup/store cycle across both files.

**Finish when you can:**
- Explain FAISS `IndexFlatIP` + L2 normalization from scratch
- Trace a cache HIT: embed → FAISS hit → Redis fetch
- Trace a cache MISS: embed → FAISS miss → eventually → Redis set + FAISS add
- Explain the stale vector problem (Redis TTL expires, FAISS key survives)
- Explain why inner product is used instead of L2 distance

---

### Step 3 — The Proxy & Failover Engine
**Sub-phases:** 2.2 → 2.5

**Why grouped:**
These two define the multi-provider story. You can't explain failover without understanding how the Router's model list and fallback map are structured.

**Finish when you can:**
- Draw the model list structure and explain each field
- Recite the fallback chains (gpt-4o → claude → gemini, gpt-3.5 → groq → gemini-flash)
- Explain what `num_retries=2` means vs. falling back
- Explain `UpstreamError` and `_map_error` and why they exist

---

### Step 4 — The Routing & Compression Layer
**Sub-phases:** 3.4 → 3.5 → 3.6

**Why grouped:**
These three form the intelligence layer that runs before cache lookup: route (which model?) → compress (shorten context?) → adaptive threshold (how strict a cache match?). They share the concept of "optimization before expensive operations."

**Finish when you can:**
- Recite the `_classify()` priority order from memory
- Explain the two compression gates (token count AND turn count)
- Explain the adaptive feedback loop in one sentence: "If cache hit rate is too high/low, tighten/loosen the similarity threshold"

---

### Step 5 — The Request Pipeline (Capstone)
**Sub-phases:** 1.4 → 1.6 → 3.7

**Why grouped:**
This is the moment everything connects. 1.4 (lifespan wiring) + 1.6 (the route handler) + 3.7 (the orchestrated call sequence inside 1.6) are one unified study session.

**Finish when you can:**
- Recite the call order in `/v1/chat/completions` from memory: route → compress → threshold → embed → search → [hit/miss branch] → telemetry
- Explain why each call happens in that specific position
- Explain what `app.state` holds and why it's used over globals
- Trace a full request end-to-end, naming which file/class handles each step

---

### Step 6 — Streaming & Remaining Proxy Details
**Sub-phases:** 1.7 → 2.3 → 2.4 → 2.6

**Why grouped:**
All streaming-related and proxy call-path sub-phases. Lower priority — study after the core is solid. Streaming especially is a useful "extra depth" question in interviews.

**Finish when you can:**
- Explain SSE protocol and `data: [DONE]`
- Explain why streaming bypasses cache and compression
- Explain `forward_with_tools()` and the provider guard

---

### Step 7 — Operational Layer (Light Pass)
**Sub-phases:** 1.1 (revisit), 1.3, 1.5, 2.7

**Why grouped:**
All operational/infra sub-phases. Don't need deep study — one quick pass to lock in the answers to operational questions in a viva ("How does health check work?" "How do you monitor requests?").

**Finish when you can:**
- Answer "how does the system expose telemetry?" in two sentences
- Answer "what does `/health` return and when would it fail?"
- Answer "how does middleware write telemetry without the route calling it?"

---

## Summary Table

| Sub-Phase | Tier | Step | Time |
|---|---|---|---|
| 3.3 Semantic Cache Orchestrator | 1 — Master | 2 | 4–5 hrs |
| 3.2 FAISS Vector Store | 1 — Master | 2 | 4–5 hrs |
| 3.7 Full Pipeline Integration | 1 — Master | 5 | 3–4 hrs |
| 2.2 LiteLLM Router Init | 1 — Master | 3 | 3–4 hrs |
| 3.6 Adaptive Threshold | 2 — Know Well | 4 | 2–3 hrs |
| 3.5 Context Compressor | 2 — Know Well | 4 | 2–3 hrs |
| 2.5 Failover & Retry | 2 — Know Well | 3 | 2–3 hrs |
| 3.4 Model Router | 2 — Know Well | 4 | 2 hrs |
| 3.1 Embedder | 2 — Know Well | 1 | 1.5–2 hrs |
| 1.7 SSE Streaming | 2 — Know Well | 6 | 2 hrs |
| 1.4 Lifespan & Wiring | 2 — Know Well | 5 | 1.5–2 hrs |
| 1.2 Models | 3 — Medium | 1 | 30 min |
| 1.1 Config | 3 — Medium | 1 | 30 min |
| 2.1 Name Resolution | 3 — Medium | 1 | 30 min |
| 2.3 Non-Streaming Forward | 3 — Medium | 6 | 30 min |
| 2.4 Streaming Forward | 3 — Medium | 6 | 30 min |
| 2.6 Tool Translation Guard | 3 — Medium | 6 | 30 min |
| 1.3 Middleware | 3 — Medium | 7 | 30 min |
| 1.5 Health & Admin | 3 — Medium | 7 | 20 min |
| 2.7 Admin API | 3 — Medium | 7 | 20 min |

**Total estimated time:** ~35–40 hours of focused study

