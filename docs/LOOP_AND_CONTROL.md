# Loop and Control: Chronological Order and DB/Config Control

This doc lists **in chronological order** how the pSEO and lead-gen loops run, what each step reads/writes in the DB, and **how much control you have** (config keys and DB state).

---

## 1. pSEO Pipeline (Campaign Loop)

Order of execution when you run the pSEO campaign (e.g. from dashboard “Run” or phase triggers):

| Step | Agent / Component | What it does | Reads (DB + config) | Writes (DB) | Your control (config / DB) |
|------|-------------------|--------------|----------------------|-------------|----------------------------|
| 1 | **Scout** | Gathers intel / anchors for the project | Project, DNA, campaign config; existing entities | Creates/updates intel entities, anchors | `pseo_default.yaml` / campaign: scout settings, limits |
| 2 | **Strategist** | Keyword/strategy run | DNA, campaign, existing intel | Strategy entities, keywords | Campaign config: strategy params |
| 3 | **Writer** | Generates page drafts | DNA, campaign config, strategy, librarian links | **page_draft** entities with `metadata.status = "draft"` | Campaign: `min_word_count`, `batch_size`; DNA content tone |
| 4 | **Critic** | QA review of drafts | Draft content, campaign/QA config | Draft `metadata.status` → `validated` or feedback | Campaign: critic checks (deterministic structure) |
| 5 | **Librarian** | Validates links, gate for “all validated” | Drafts, link config | Draft status → `ready_for_media` when links validated; link order | Campaign: link validation; “all validated” gate |
| 6 | **Media** | Fetches/selects images | Drafts, DNA, campaign | Draft `metadata` (images, media) → `ready_for_utility` | Campaign: `brand_image_keywords`, `fallback_image_url` |
| 7 | **Utility** | Injects form, schema, call button; **post-Utility validator** | Draft HTML, lead_gen config (form/schema/call templates), campaign | Draft → `ready_to_publish` or `utility_validation_failed` + reason | Campaign/DNA: `form_template`, `schema_template`, `call_button_template`, `form_webhook_path`; validator checks webhook, `tel:` link, JSON-LD |
| 8 | **Publisher** | Publishes ready drafts | Drafts with `ready_to_publish` | Draft → `published`; external publish (e.g. CMS) | Publish target config |

- **DB entities:** `page_draft` (status progression), intel/strategy/anchors as used by each agent.
- **Config:** Project DNA + campaign config (YAML + dashboard-editable). Campaign GET/PATCH at `GET/PATCH /api/projects/{project_id}/campaigns/{campaign_id}`.

---

## 2. Lead-Gen Flow (Voice Bridge + Forms)

Chronological order from inbound lead to bridge:

| Step | Trigger | What it does | Reads (DB + config) | Writes (DB) | Your control |
|------|---------|---------------|----------------------|-------------|--------------|
| 1 | **Webhook** (e.g. WordPress, Google Ads, or `/api/webhooks/lead`) | Receives form/post; creates **lead** entity | Project/campaign from query or payload | **lead** entity (`metadata.source`, `metadata.data`) | Webhook URL, `project_id` (and optional `campaign_id`) in request |
| 2 | **lead_received** (LeadGenManager) | Dispatches **lead_scorer** | Lead, DNA + campaign config | — | Campaign: lead_gen config |
| 3 | **lead_scorer** | Scores lead | Lead, scoring config | Lead `metadata` (score, etc.) | Scoring thresholds in config |
| 4 | **lead_received** (cont.) | If `score >= min_score_to_ring`: sets **scheduled_bridge_at** = now + `bridge_delay_minutes`, sends bridge-review email | `sales_bridge.business_hours`, `bridge_delay_minutes`, `bridge_review_email` | Lead `metadata.scheduled_bridge_at`, `metadata.bridge_status = "scheduled"` | `lead_gen_default.yaml` / campaign: `min_score_to_ring`, `bridge_delay_minutes`, `bridge_review_email`, `business_hours`, `days_of_week` |
| 5 | **process_scheduled_bridges** (cron or API) | Runs periodically (e.g. every 1–2 min); finds leads with `scheduled_bridge_at <= now`, `bridge_status == "scheduled"`; for each, if **within business hours** (and **days_of_week**), dispatches **instant_call** | Leads (project), `business_hours`, `days_of_week` | Lead `metadata.bridge_status = "bridge_attempted"` after attempt | Call **POST /api/projects/{project_id}/lead-gen/process-scheduled-bridges** (cron or frontend poll); config: `business_hours`, `days_of_week` |
| 6 | **instant_call** (LeadGenManager → SalesAgent) | Twilio: call boss (destination_phone), then bridge to customer | `within_business_hours` + `days_of_week`; `sales_bridge.destination_phone` | Lead `metadata` (call_sid, recording_url, etc.) | Campaign: `sales_bridge.destination_phone`, `business_hours`, `days_of_week`; manual “Connect call” also triggers this |

- **DB entities:** **lead** (`metadata`: `scheduled_bridge_at`, `bridge_status`, `call_sid`, `recording_url`, score, etc.).
- **Config:** `lead_gen_default.yaml` and campaign config (dashboard): `sales_bridge`, `business_hours` (incl. `days_of_week`), `bridge_delay_minutes`, `min_score_to_ring`, `bridge_review_email`, and template overrides (`form_template`, `schema_template`, `call_button_template`, `form_webhook_path`).

---

## 3. Summary: Control You Have

- **pSEO loop:** Control via **campaign config** (and DNA): Writer word count/batch, Critic checks, Librarian gate/link order, Media image keywords/fallback, Utility templates and post-Utility validator (form webhook, tel link, JSON-LD). DB: draft statuses; you can re-run phases or fix drafts and re-run from a phase.
- **Lead-gen loop:** Control via **campaign/config**: scoring, bridge delay, business hours and days, destination phone, email; **scheduled bridges** run only when you call the process-scheduled-bridges API (cron recommended). DB: lead `scheduled_bridge_at`, `bridge_status`; you can change delay/hours/days and who gets the bridge email.

---

## 4. API Quick Reference

- **Campaign (get/update):** `GET/PATCH /api/projects/{project_id}/campaigns/{campaign_id}` — edit campaign config (includes lead_gen templates, sales_bridge, business_hours).
- **Process scheduled bridges:** `POST /api/projects/{project_id}/lead-gen/process-scheduled-bridges` — call periodically (e.g. cron every 1–2 min) to run the 10‑minute-delayed voice bridge within business hours.
