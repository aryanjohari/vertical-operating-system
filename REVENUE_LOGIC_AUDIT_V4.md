# Revenue Logic Audit v4 — Campaign Architecture

**Date:** January 2026  
**Scope:** v4 codebase (branch `v4-campaign-architecture`)  
**Objective:** Assess whether the pSEO and lead-gen pipelines produce professional-grade, revenue-ready output.

---

## Executive Summary

**Profitability score (v4): 5/10**

The v4 campaign architecture improves structure (campaign-scoped entities, mining, RAG, modular config) but **content and lead flows still under-inject real data**. The pipeline is technically sound; the main gaps are **hard data injection** (pricing, local procedures, social proof) and **lead qualification**. Until those are upgraded, pages will remain templated and conversion suboptimal.

---

## 1. Strategy Trace (Data Transformation) — v4

### End-to-End Flow

```
Campaign config (targeting, mining_requirements)
    ↓
ScoutAgent: maps_sync (anchors) + search_sync (competitor/fact)
    ↓
anchor_location + knowledge_fragment entities (campaign_id)
    ↓
StrategistAgent: seo_keyword entities (pending, anchor_reference)
    ↓
WriterAgent: RAG + knowledge_fragment + optional anchor → page_draft (draft)
    ↓
Critic → Librarian → Media → Utility → Publisher
    ↓
page_draft (published) → WordPress
```

### Step 1: Input (Scout)

- **Source:** Campaign `targeting` (service_focus, geo_targets) and `mining_requirements` (geo_context.target_anchors, competitor, regulatory).
- **Maps:** `run_scout_sync` (Playwright, Google Maps). Queries like `"Court in Auckland"`, `"Police Station in Manukau"`. Output: name, address, maps URL, phone.
- **Search:** `run_search_sync` (Serper). Competitor queries (e.g. `"average cost of {service} {city}"`), regulatory (`"official filing fee for {service} in {city}"`). Stored as `knowledge_fragment` with `fragment_type` (competitor/fact), `url`, `snippet`.
- **Strengths:** Real locations (Maps); real snippets (Serper). Campaign-scoped.
- **Gaps:** No structured extraction of “filing fee = $X” or “processing time = Y days”. Snippets are raw; Writer uses them as context only.

### Step 2: Keyword Strategy (Strategist)

- **Input:** `anchor_location` entities + campaign `targeting.service_focus`, `geo_targets`.
- **Output:** `seo_keyword` entities with `cluster_data`, `anchor_reference`, `status: pending`.
- **Gaps:** No search-volume or intent data. Keywords remain template-driven (service + location swaps).

### Step 3: Content Generation (Writer)

- **Input:** Pending keyword, optional `anchor_reference`, RAG (ChromaDB) + `knowledge_fragment` (SQL), campaign/DNA.
- **Anchor:** Writer resolves anchor via `memory.get_entity(anchor_ref_id, user_id)`. **Known bug:** `get_entity` is not implemented; anchor context can be missing.
- **Prompt:** Uses `anchor_data` (name, address) for “minutes away from {anchor}” and local paragraph; `intel_context` from knowledge fragments for “Regulatory Reality” and citations. Placeholders `{{image_main}}`, `{{form_capture}}`.
- **Strengths:** Explicit “use KNOWLEDGE BANK,” anchor + intel in prompt.
- **Gaps:**
  - No **structured** pricing tables (e.g. “filing fee $X”). Intel is prose/snippets, not structured fields.
  - No **location-specific** procedures (e.g. “Auckland District Court requires X forms”).
  - No real reviews, case studies, or permit data.
  - `get_entity` missing → anchor-based localisation often skipped.

### Step 4: Quality & Enrichment (Critic → Utility)

- **Critic:** PASS/FAIL, score ≥ 7 → validated. Checks brand voice, forbidden topics, structure (`<h1>`, `{{form_capture}}`).
- **Librarian:** Internal links + “References” from `knowledge_fragment`.
- **Media:** Unsplash image → `{{image_main}}`.
- **Utility:** JSON-LD schema; `{{form_capture}}` replaced with conversion asset (or generic CTA) if lead_gen enabled.
- **Gaps:** Critic validates structure and tone, not “amount of real data” or uniqueness. No uniqueness scoring.

### Step 5: Publish

- **Publisher:** WordPress REST API; `ready_to_publish` → `published`, `live_url` stored.
- **Config:** Campaign `cms_settings` or DNA `local_seo.publisher_settings`; password in `client_secrets`.

### Data-Transformation Summary (v4)

```
Maps + Serper → anchor_location + knowledge_fragment (real but unstructured)
    ↓
Strategist → seo_keyword (template-style clusters)
    ↓
Writer → page_draft (LLM prose + intel context; no structured pricing/procedures)
    ↓
Critic / Librarian / Media / Utility → structure, links, images, schema, form
    ↓
Publisher → live page (low uniqueness vs. competitor pages)
```

**Verdict:** v4 adds a real **intel layer** (Scout mining, knowledge_fragment, Writer citation). The pipeline is still **enrichment-light**: no structured pricing, no local procedures, no social proof. Content stays **template-like** despite better scaffolding.

---

## 2. “Spam vs. Utility” Check — v4

### Uniqueness

- **Template similarity:** Still high. H1 = keyword; H2 = context keywords; body = “minutes away from {anchor}” + intel-based paragraph + generic CTA. Same pattern across locations.
- **Value-add:** Improved vs. pre-v4 (citations, mining) but **2/10** on “hard data”:
  - No pricing tables, no “filing fee $X,” no payment options.
  - No court-/council-specific procedures or document lists.
  - No real testimonials, case studies, or trust badges.
  - No competitor comparison with real numbers.

### What Exists in v4

- Anchor name/address (when `get_entity` works) and “minutes away” copy.
- Knowledge-fragment snippets (competitor/fact) cited in body and “References.”
- DNA brand voice, forbidden topics; Critic enforcement.
- `{{form_capture}}` and Utility-injected conversion block; JSON-LD.

### What’s Missing

- **Structured** regulatory/commercial data (costs, processing times, required documents).
- **Location-specific** procedures (e.g. Auckland vs. Wellington court rules).
- **Social proof** (reviews, case outcomes, certifications).
- **Uniqueness scoring** (e.g. Critic or post-Writer check for template overlap).

**Verdict:** v4 is **better than generic AI spam** (mining, RAG, campaign config) but still **utility-light**. Without structured data injection, pages remain **template-style** and weakly differentiated.

---

## 3. Lead-Trap Assessment — v4

### CTA and Forms

- **Writer:** `{{form_capture}}` placeholder.
- **Utility:** Replaces with `conversion_asset.html_code` from config or generic “Get Immediate Help” CTA. Form can be injected into content or appended.
- **Lead Gen:** Lead-gen campaign config (bridge, sniper, etc.) is separate from pSEO; form injection is the main crossover.

### Urgency and Friction

- **Urgency:** “Call immediately,” phone number, CTA. No time-bound offer (“24/7,” “callback in 15 min”) or scarcity.
- **Friction:** Form typically name, phone, message. Low friction; no pre-qualification.

### Lead Quality and Bridge

- **Flow:** Form → webhook → lead entity → optional **SalesAgent** bridge.
- **Scoring:** **LeadScorerAgent** updates `metadata.score`; **Sniper**-sourced leads can be auto-scored post-hunt. No **form-side** qualification (e.g. “When do you need help?”).
- **Bridge:** Boss receives call; “Press 1” to connect. High-intent experience, but **all** form submits can trigger bridge if so configured; no filter by urgency or fit.

**Verdict:** Lead capture is **functional**; bridge is a strength. **Lead qualification** (pre-bridge) and **urgency/scarcity** in CTAs are still missing → risk of wasted boss time on low-intent leads.

---

## 4. Verdict and Scorecard — v4

### Profitability Score: **5/10**

| Dimension | Score | Notes |
|-----------|-------|--------|
| Technical architecture | 8/10 | Campaigns, config merge, pipeline, mining, RAG |
| Content quality | 4/10 | Better intel use; still templated, no hard data |
| Data enrichment | 2/10 | Snippets only; no structured pricing/procedures |
| Lead capture | 6/10 | Works; bridge good; no qualification |
| Uniqueness | 3/10 | Mining helps; structure still repetitive |

### Revenue Implication (Ballpark)

- **Assumptions:** 100 pages; ~1.5% CTR; ~3% form conversion; $500 AOV; 25% close.
- **Rough MRR:** ~\$56. Without better data and qualification, growth ceiling remains low.

**Verdict:** v4 is **production-capable** and **architecturally solid**, but **revenue-ready** only after **data-injection** and **lead-qualification** upgrades.

---

## 5. Upgrade Plan — v4-Specific

### Priority 1: Fix `memory.get_entity` (Critical)

- **Where:** `backend/core/memory.py`.
- **What:** Implement `get_entity(entity_id: str, tenant_id: str) -> Optional[dict]` (e.g. `SELECT * FROM entities WHERE id = ? AND tenant_id = ?`, return row as dict with `metadata` parsed).
- **Impact:** Writer and Manager (`force_approve_draft`) stop failing on anchor resolution; “minutes away from {anchor}” and local copy work.

### Priority 2: Structured Intel Extraction (High)

- **Where:** Post–Scout, pre-Writer (or Scout output processing).
- **What:** Parse Serper snippets (or dedicated scrape) into structured fields: e.g. `filing_fee`, `processing_days`, `official_source_url`, `price_range`. Store in `knowledge_fragment.metadata` or new structure.
- **Writer:** Prompt instructs “use ONLY these structured fields” for pricing/procedures; emit a small **pricing/procedure block** (e.g. table or bullet list) in HTML.
- **Impact:** Pages contain **verifiable, structured data** → higher trust and uniqueness.

### Priority 3: Location-Specific Procedures (High)

- **Where:** Campaign config and/or Miner.
- **What:** Per-city (or per-court/council) procedures: required documents, steps, deadlines. Stored as structured config or mined intel.
- **Writer:** Injects “How it works in {city}” / “Documents you need” using that data.
- **Impact:** Strong local relevance and E-E-A-T.

### Priority 4: Lead Qualification and Urgency (Medium)

- **Where:** Form + webhook + optional Manager logic.
- **What:**
  - Form: “When do you need help?” (emergency / this week / planning). Optional “What service?” dropdown.
  - Webhook / bridge logic: Only trigger bridge for “emergency” / “urgent” (or score threshold); others go to nurture.
  - CTA: “Available 24/7,” “Callback in 15 minutes,” “X clients helped in {city}.”
- **Impact:** Fewer low-intent bridge calls; higher close rate and boss satisfaction.

### Priority 5: Uniqueness and Quality Metrics (Medium)

- **Where:** Critic or post-Writer step.
- **What:** Uniqueness check (e.g. overlap vs. other drafts or live pages). Reject or flag pages above ~80% similarity. Optional “data density” check (e.g. presence of pricing/procedure block).
- **Impact:** Less template duplication; better long-term SEO.

### Priority 6: Social Proof and Schema (Lower)

- **Where:** DNA/campaign config, Writer, Utility.
- **What:** Optional testimonials, case outcomes, certifications; `AggregateRating` / `Review` schema where valid. Utility already adds JSON-LD; extend with `PriceRange` when pricing exists.
- **Impact:** Trust and SERP richness.

---

## 6. Implementation Notes (v4 Codebase)

### Config and Campaigns

- **DNA:** `identity`, `brand_brain`, `modules` in `profile_template.yaml`; `dna.generated.yaml` + `dna.custom.yaml` per project.
- **Campaign:** `pseo_default.yaml` / `lead_gen_default.yaml`; DB `campaigns.config`; optional `data/profiles/{project_id}/campaigns/{campaign_id}.yaml`.
- **Merge:** `ConfigLoader.load(project_id, campaign_id)`; campaign overrides `modules[module]`.

### Entities and Pipeline

- **Campaign-scoped:** `anchor_location`, `knowledge_fragment`, `seo_keyword`, `page_draft`, `lead` use `metadata.campaign_id`.
- **Draft status flow:**  
  `draft` → Critic → `validated` | `rejected` → Librarian → `ready_for_media` → Media → `ready_for_utility` → Utility → `ready_to_publish` → Publisher → `published`.

### Mining and RAG

- **Scout:** `maps_sync` (Maps) + `search_sync` (Serper competitor/fact). `knowledge_fragment` typed by `fragment_type`.
- **Writer:** ChromaDB `query_context` (project/campaign filter) + SQL `knowledge_fragment`; prompt cites “KNOWLEDGE BANK” and anchor.

### Leads and Bridge

- **Lead Gen Manager:** `hunt_sniper`, `ignite_reactivation`, `instant_call`, `transcribe_call`, `dashboard_stats`. Uses `campaign_id` and merged config.
- **Bridge:** SalesAgent; DNA/campaign `bridge` (destination_phone, whisper, sms_alert).

---

## 7. Summary

- **v4** delivers a clear **campaign architecture**, **mining**, **RAG**, and **modular config**, and improves traceability and maintainability.
- **Revenue logic** still lags: **structured data injection** (pricing, procedures) and **lead qualification** are the main gaps.
- **Immediate:** Implement `get_entity` and add **structured intel extraction** + Writer injection.
- **Next:** Location-specific procedures, qualification/urgency, and uniqueness checks.

**Report version:** 4.0  
**Codebase branch:** v4-campaign-architecture  
**Last updated:** January 2026
