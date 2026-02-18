# Plan: Decouple YAML from Frontend and Backend (Schema-Driven Forms)

## Objective

Make YAML templates the single source of truth. Changing YAML alone should drive forms and config without editing frontend or Genesis. Preserve kernel validation and error handling patterns.

---

## 1. YAML Schema Convention

Add a lightweight schema layer. Two options:

### Option A: Sidecar schema files (explicit)
- `profile_template.yaml` + `profile_template.schema.json` (or `.yaml`)
- Schema defines: field path, type (string, array, number, boolean, object), required, label, placeholder
- YAML stays as-is; schema is the contract for form generation and validation

### Option B: Infer from YAML + metadata comments
- Parse YAML structure: leaf `string` → text input, `list` → textarea (newline-separated) or add-row, `object` → section, `boolean` → checkbox
- Use value `"REQUIRED"` or key suffix `_required` for required fields
- No extra files; schema derived at runtime from YAML

**Recommendation:** Option B for minimal change; Option A if you need fine-grained control (e.g. dropdown options, custom widgets).

---

## 2. Backend: Schema Service

### 2.1 New module: `backend/core/schema_loader.py`

- `load_yaml_template(template_name: str) -> dict`  
  Load template from `core/templates/{template_name}.yaml`.

- `yaml_to_form_schema(yaml_doc: dict) -> dict`  
  Walk YAML and produce a form schema:
  - For each leaf: `{ path, type, required, default, label? }`
  - For lists: `{ path, type: "array", itemType: "string"|"object", ... }`
  - For nested objects: `{ path, type: "object", children: [...] }`
  - Use `"REQUIRED"` as value to mark required; empty string/empty list = optional

- `merge_form_into_template(template: dict, form_data: dict) -> dict`  
  Deep merge: form values override template defaults. Handle:
  - String → string
  - Array from form: string (newline-separated) → list, or list → list
  - Boolean, number coercion

- `validate_required(schema: dict, merged: dict) -> tuple[bool, str]`  
  Check required fields. Return `(True, "")` or `(False, "error message")`.

### 2.2 New API routes: `backend/routers/schemas.py`

- `GET /api/schemas/profile`  
  Returns form schema for profile (from `profile_template.yaml`).
- `GET /api/schemas/campaign/pseo`  
  Returns form schema for pSEO campaign.
- `GET /api/schemas/campaign/lead_gen`  
  Returns form schema for lead_gen campaign.

Each response shape:
```json
{
  "schema": { "sections": [...], "fields": [...] },
  "defaults": { ... }
}
```

Use kernel-compatible error handling: return 500 with message on YAML load/parse failure.

---

## 3. Genesis Refactor

### 3.1 Replace hardcoded build functions

- Remove `_build_dna_from_form`, `_build_pseo_config_from_form`, `_build_lead_gen_config_from_form`.
- Add generic `_build_config_from_form(template_name: str, form_data: dict) -> dict`:
  1. Load YAML template via `schema_loader.load_yaml_template(template_name)`.
  2. Call `schema_loader.merge_form_into_template(template, form_data)`.
  3. Call `schema_loader.validate_required(schema, merged)`.
  4. If invalid → `return AgentOutput(status="error", message=error_msg)`.
  5. Return merged dict.

### 3.2 Update `_compile_profile` and `_create_campaign`

- `_compile_profile`: Call `_build_config_from_form("profile_template", profile)` instead of `_build_dna_from_form`.
- `_create_campaign`: Call `_build_config_from_form(f"{module}_default", form_data)` instead of module-specific builders.

### 3.3 Keep existing behavior

- `_save_profile` unchanged (ConfigLoader, memory, RAG injection).
- `_validate_dna_structure` can be replaced by schema-based validation or kept for profile-specific checks.
- Same `AgentOutput(status="error", message="...")` pattern for all failures.

---

## 4. Kernel Validation

- **No change** to `OnboardingParams` or `TASK_SCHEMA_MAP`.
- Kernel validates envelope: `action`, `project_id`, `module`, `form_data`/`profile` as `Dict[str, Any]`.
- Structure validation (required fields, types) happens **inside Genesis** using the schema, not in kernel.
- Errors surface as `AgentOutput(status="error", message="...")` as today.

---

## 5. Frontend: Dynamic Form Renderer

### 5.1 New component: `components/forms/DynamicForm.tsx`

- Props: `schema` (from API), `defaults`, `onSubmit`, `submitLabel`, `loading`.
- Fetches schema on mount if not passed, or parent fetches and passes.
- Renders form by iterating schema:
  - `string` → `<input type="text">` or `<select>` if options provided
  - `array` (itemType string) → `<textarea>` with one-per-line hint
  - `boolean` → `<input type="checkbox">`
  - `number` → `<input type="number">`
  - `object` → section header + recursive `DynamicForm` or field group
- Uses existing styling: `inputClass`, `glass-panel`, `acid-glow`.
- On submit: build payload from form state (align with schema paths), call `onSubmit(payload)`.

### 5.2 New API function: `lib/api.ts`

- `getFormSchema(type: "profile" | "pseo" | "lead_gen")`  
  Calls `GET /api/schemas/profile` or `/api/schemas/campaign/pseo` or `lead_gen`.

### 5.3 Replace hardcoded dialogs

- **CreateProjectDialog**: Fetch profile schema, render `DynamicForm`, submit to `createProjectWithProfile(payload)`.
- **CreateCampaignDialog**: Fetch campaign schema by module, render `DynamicForm`, submit to `createCampaignWithForm(projectId, module, payload)`.

### 5.4 Fallback

- If schema fetch fails: show error toast, optionally show a minimal fallback form (e.g. only required fields) or "Try again" button.

---

## 6. Error Handling (Same as Today)

- **Backend**: Genesis returns `AgentOutput(status="error", message="...")` for validation/save failures.
- **API routes**: Projects router returns 400/500 with `detail=result.message` when kernel returns error.
- **Frontend**: Toast on error; keep dialog open so user can correct.

---

## 7. File and Data Flow

```
YAML (profile_template.yaml, pseo_default.yaml, lead_gen_default.yaml)
    │
    ▼
schema_loader.py  ──► GET /api/schemas/{type}
    │                       │
    │                       ▼
    │                  DynamicForm (frontend)
    │                       │
    │                       ▼
    │                  form_data (JSON)
    │                       │
    ▼                       ▼
merge_form_into_template(template, form_data)
    │
    ▼
validate_required(schema, merged)
    │
    ▼
Genesis: _build_config_from_form() → merged config
    │
    ▼
_save_profile (profile) / memory.create_campaign + config_loader.save_campaign (campaign)
```

---

## 8. Implementation Order

1. Implement `backend/core/schema_loader.py` (load, infer schema, merge, validate).
2. Add `GET /api/schemas/*` routes.
3. Refactor Genesis to use `_build_config_from_form`.
4. Build `DynamicForm` component and wire to schemas.
5. Replace CreateProjectDialog and CreateCampaignDialog with schema-driven versions.
6. Test all flows; add fallback and error handling.

---

## 9. What Stays the Same

- Kernel dispatch, OnboardingParams, AgentOutput.
- ConfigLoader, memory, RAG injection.
- API contracts: POST /api/projects with profile, POST /api/projects/{id}/campaigns with form_data.
- UI look and feel (glass-panel, acid-glow, same layout).
- Scout/Writer/other agents: they still read campaign/profile config from memory/ConfigLoader; config shape is unchanged.
