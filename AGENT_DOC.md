3. **Context Gathering**
   - Extracts keyword name (e.g., "get out of jail help Auckland 1010")
   - Extracts city from keyword metadata
   - Extracts target anchor name (e.g., "Auckland District Court")
   - Loads hardcoded values (MVP): phone number, USPs (Unique Selling Points)

4. **Internal Link Discovery** (Mini-Librarian)
   - Finds sibling keywords in the same city
   - Randomly selects up to 5 related keywords to link to
   - Generates HTML list of internal links: `<h3>Other Services in {city}</h3><ul>...</ul>`
   - Enhances SEO through internal linking structure

5. **AI Content Generation**
   - Constructs system instruction for Gemini:
     - Expert SEO Copywriter persona
     - Rules: HTML only (no markdown), 600 words, structured sections
     - Must mention target entity & address 3x for SEO
   - Builds user prompt with:
     - Keyword title
     - Target anchor and city
     - Phone number and USPs
   - Calls Gemini with system instruction and user prompt
   - Temperature: 0.7 (balanced creativity/consistency)

6. **Content Processing**
   - Cleans AI response: removes markdown code blocks
   - Converts markdown bold (`**text**`) to HTML (`<strong>text</strong>`)
   - Generates Schema.org JSON-LD via `_generate_schema()`:
     - LocalBusiness type
     - Includes name, telephone, address, areaServed
   - Assembles final HTML: content + internal links + schema

7. **Page Entity Creation**
   - Creates `page_draft` entity:
     - `id`: `f"page_{keyword_id}"`
     - `entity_type`: `"page_draft"`
     - `name`: Keyword string
     - `metadata`:
       - `keyword_id`: Links back to source keyword
       - `content`: Full HTML (content + links + schema)
       - `status`: `"draft"` (will be enhanced by Media/Utility agents)
       - `city`: City name

8. **Keyword Status Update**
   - Updates source keyword entity:
     - Changes `status` from `"pending"` to `"published"`
     - Preserves all other metadata
   - Marks keyword as processed

### Input/Output

#### Input (`AgentInput`)
```python
{
    "task": "write_pages",
    "user_id": "admin@admin.com",
    "params": {}
}
```

#### Output (`AgentOutput`)
```python
{
    "status": "success",
    "message": "Drafted 1 pages with internal links.",
    "data": {"count": 1}
}
```

### Dependencies

- **Google Gemini API**: `google-genai` library with system instructions
- **Environment Variable**: `GOOGLE_API_KEY`
- **Database**: `memory.get_entities()`, `memory.save_entity()`
- **DNA Profile**: Not heavily used (hardcoded values in MVP)

### Configuration Requirements

- DNA profile loaded but uses hardcoded values for MVP:
  - Phone: "0800-LEG-AID"
  - USPs: "- 24/7 Availability\n- No Win No Fee\n- Local Experts"

### Example Usage

```python
# Triggered by Manager Agent in Phase 3
payload = {
    "task": "write_pages",
    "user_id": "admin@admin.com",
    "params": {}
}
```

### Error Handling

- **No Pending Keywords**: Returns "complete" status if nothing to write
- **AI Generation Failure**: Catches exceptions, logs error, continues with next keyword
- **Save Failures**: Continues processing even if individual saves fail
- **Rate Limiting**: 1-second delay between requests to respect API limits

### Key Features

- **AI-Powered Content**: Uses Gemini with system instructions for quality
- **Internal Linking**: Automatically links related pages in same city
- **Schema.org Markup**: Generates structured data for SEO
- **Status Management**: Updates keyword status to "published"
- **Deduplication**: Prevents writing same keyword twice
- **Batch Processing**: Configurable batch size (currently 1, can be increased)

---

## 6. Media Agent

**File**: `backend/agents/media.py`  
**Class**: `MediaAgent`  
**Task Name**: `enhance_media`  
**Profile Required**: ✅ Yes

### Purpose

Adds visual elements to page drafts using Unsplash API. Enhances pages with professional cityscape images that match the page's location.

### How It Works

#### Step-by-Step Process

1. **Draft Fetching**
   - Fetches all `page_draft` entities from database
   - Filters for drafts that:
     - Have `status: "draft"`
     - Do NOT have `image_url` in metadata
   - Returns "complete" if no pages need images

2. **Batch Processing**
   - Processes up to 5 pages at a time
   - Uses structured logging via `self.logger`

3. **Smart Query Construction** (The "Zip Code Killer")
   - Extracts raw city from page metadata (e.g., "Auckland 1010")
   - Removes all numbers using regex: `re.sub(r'\d+', '', raw_city)`
   - Result: "Auckland 1010" → "Auckland"
   - Constructs universal query: `"{clean_city} city architecture"`
   - **Why "city architecture"?**: Works universally for any business type (lawyers, plumbers, cafes) and guarantees professional results

4. **Unsplash API Search**
   - **Fallback Image**: Pre-configured placeholder if API fails
     - URL: `https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b`
   - **If No API Key**: Uses fallback, logs warning
   - **If API Key Present**:
     - Calls: `https://api.unsplash.com/search/photos?query={query}&per_page=1&orientation=landscape`
     - Extracts first result's `urls.regular`
     - Extracts photographer credit: `"Photo by {name} on Unsplash"`
   - **Error Handling**:
     - Zero results → Uses fallback
     - API error → Logs error with status code and response body, uses fallback
     - Always returns valid image URL

5. **HTML Image Injection**
   - Creates HTML div with:
     - Featured image with responsive styling
     - Border radius and box shadow for polish
     - Photographer credit in small text
   - Prepends image HTML to page content (appears at top)

6. **Metadata Update**
   - Updates page entity metadata:
     - Adds `image_url`: Unsplash image URL
     - Prepends image HTML to `content` field
   - Uses `memory.update_entity()` to merge changes

### Input/Output

#### Input (`AgentInput`)
```python
{
    "task": "enhance_media",
    "user_id": "admin@admin.com",
    "params": {}
}
```

#### Output (`AgentOutput`)
```python
{
    "status": "success",
    "message": "Enhanced 5 pages with visuals.",
    "data": {"count": 5}
}
```

### Dependencies

- **Unsplash API**: `requests` library for HTTP calls
- **Environment Variable**: `UNSPLASH_ACCESS_KEY` (optional, has fallback)
- **Database**: `memory.get_entities()`, `memory.update_entity()`
- **Regex**: For city name cleaning

### Configuration Requirements

None (uses universal "city architecture" query strategy)

### Example Usage

```python
# Triggered by Manager Agent in Phase 4a
payload = {
    "task": "enhance_media",
    "user_id": "admin@admin.com",
    "params": {}
}
```

### Error Handling

- **No Pages Needing Images**: Returns "complete" status
- **Missing API Key**: Uses fallback image, logs warning
- **API Failures**: Comprehensive error logging with status codes and response bodies
- **Zero Results**: Uses fallback image, logs warning
- **Individual Page Failures**: Continues processing other pages, logs errors with full traceback

### Key Features

- **Universal Query Strategy**: "city architecture" works for any business type
- **Zip Code Removal**: Automatically cleans city names (removes postcodes)
- **Fallback System**: Always returns valid image (never fails completely)
- **Professional Styling**: Inline CSS for responsive, polished images
- **Attribution**: Includes photographer credits (Unsplash requirement)
- **Non-Destructive**: Prepends image, doesn't replace content

---

## 7. Utility Agent

**File**: `backend/agents/utility.py`  
**Class**: `UtilityAgent`  
**Task Name**: `enhance_utility`  
**Profile Required**: ✅ Yes

### Purpose

Adds interactive JavaScript tools/widgets to pages for lead capture. Generates functional calculators, quizzes, or contact forms that capture leads and send them to the backend API.

### How It Works

#### Step-by-Step Process

1. **Draft Fetching**
   - Fetches all `page_draft` entities from database
   - Filters for drafts that:
     - Have `image_url` in metadata (Media Agent must run first)
     - Do NOT have `has_tool` in metadata
   - Returns "complete" if no pages need tools

2. **Batch Processing**
   - Processes up to 5 pages at a time

3. **Tool Type Detection** (Heuristic-Based)
   - Analyzes keyword name to determine tool type:
     - If "bail" in keyword → `"Bail Cost Estimator"`
     - If "aid" in keyword → `"Legal Aid Eligibility Quiz"`
     - Otherwise → `"Simple Contact Form"`
   - Extracts location from keyword (splits by " in ", takes last part)

4. **Source Label Generation**
   - Creates source label: `"{tool_type} - {location}"`
   - Example: `"Bail Cost Estimator - Auckland"`
   - Used for lead tracking in backend

5. **AI Tool Generation**
   - Constructs detailed prompt for Gemini:
     - Tool type and context (keyword)
     - Requirements:
       1. Clean CSS styling (inside `<style>` tags)
       2. Relevant inputs (name, phone, email, charges, urgency, etc.)
       3. Calculate/Check button
       4. **CRITICAL**: Form submission handler that:
          - Prevents default form submission
          - Collects all form data into JavaScript object
          - POSTs to `http://localhost:8000/api/leads` with JSON payload:
            ```json
            {
              "user_id": "{user_id}",
              "project_id": "{project_id}",
              "source": "{source_label}",
              "data": { /* all form inputs */ }
            }
            ```
          - Includes proper headers: `Content-Type: application/json`
          - Handles response (shows success/error message)
          - Logs to console for debugging
     - Returns ONLY HTML string (no markdown)

6. **HTML Injection**
   - Gets current page content
   - If FAQs section exists: Injects tool before `<h2>Frequently Asked Questions`
   - Otherwise: Appends tool to end of content
   - Wraps tool in `<div class='tool-section'>` for styling

7. **Metadata Update**
   - Updates page entity metadata:
     - Updates `content` with tool HTML injected
     - Sets `has_tool: True` flag
   - Uses `memory.update_entity()` to merge changes

### Input/Output

#### Input (`AgentInput`)
```python
{
    "task": "enhance_utility",
    "user_id": "admin@admin.com",
    "params": {}
}
```

#### Output (`AgentOutput`)
```python
{
    "status": "success",
    "message": "Added interactive tools to 5 pages.",
    "data": {}
}
```

### Dependencies

- **Google Gemini API**: `google-genai` library
- **Environment Variable**: `GOOGLE_API_KEY`
- **Database**: `memory.get_entities()`, `memory.update_entity()`
- **Lead API**: Tools POST to `/api/leads` endpoint

### Configuration Requirements

None (tool types determined heuristically from keywords)

### Example Usage

```python
# Triggered by Manager Agent in Phase 4b
payload = {
    "task": "enhance_utility",
    "user_id": "admin@admin.com",
    "params": {}
}
```

### Error Handling

- **No Pages Needing Tools**: Returns "complete" status
- **AI Generation Failure**: Catches exceptions, logs error, continues with next page
- **Individual Page Failures**: Continues processing other pages

### Key Features

- **AI-Generated Tools**: Uses Gemini to create functional JavaScript widgets
- **Lead Capture Integration**: Tools automatically POST to `/api/leads` endpoint
- **Multiple Tool Types**: Bail Calculator, Eligibility Quiz, Contact Form
- **Smart Placement**: Injects before FAQs for better UX
- **Self-Contained**: CSS and JavaScript embedded in HTML
- **Error Handling**: Client-side error handling in generated code
- **Source Tracking**: Each tool includes source label for lead attribution

### Generated Tool Structure

Example generated tool includes:
- **HTML Form**: Inputs relevant to tool type
- **CSS Styling**: Embedded in `<style>` tags
- **JavaScript Handler**: 
  - Form submission prevention
  - Data collection
  - Fetch API call to backend
  - Success/error message display
  - Console logging for debugging

---

## 8. Publisher Agent

**File**: `backend/agents/publisher.py`  
**Class**: `PublisherAgent`  
**Task Name**: `publish`  
**Profile Required**: ✅ Yes

### Purpose

Publishes completed page drafts to CMS platforms (WordPress or Vercel). Marks pages as published in the database after successful deployment.

### How It Works

#### Step-by-Step Process

1. **Credential Retrieval**
   - Gets WordPress credentials from database: `memory.get_client_secrets(user_id)`
   - Returns error if credentials not found (user must set up credentials first)
   - Extracts: `wp_url`, `wp_user`, `wp_password`

2. **Ready Page Filtering**
   - Fetches all `page_draft` entities
   - Filters for pages that:
     - Have `has_tool: True` (fully enhanced)
     - Do NOT have `status` in `['published', 'live']` (not already published)

3. **Publishing Loop**
   - Iterates through ready pages
   - Calls appropriate publish method based on `self.target`:
     - `"wordpress"` → `publish_to_wordpress()`
     - `"vercel"` → `publish_to_github()` (placeholder)

4. **WordPress Publishing** (`publish_to_wordpress()`)
   - **Authentication**: Base64 encodes credentials: `base64.b64encode(f"{wp_user}:{wp_password}")`
   - **Request Construction**:
     - URL: WordPress REST API endpoint (from `wp_url`)
     - Method: POST
     - Headers: `Authorization: Basic {encoded_creds}`
     - Body (JSON):
       ```json
       {
         "title": page['name'],
         "content": page['metadata']['content'],
         "status": "draft",  // Publishes as draft first (safe)
         "categories": [1]   // Default category
       }
       ```
   - **Response Handling**: Returns `True` if status code is 201 (created)

5. **Status Update**
   - If publish successful:
     - Updates page metadata: `status: "published"`
     - Uses `memory.update_entity()` to save changes
   - Counts successful publishes

### Input/Output

#### Input (`AgentInput`)
```python
{
    "task": "publish",
    "user_id": "admin@admin.com",
    "params": {}
}
```

#### Output (`AgentOutput`)
```python
{
    "status": "success",
    "message": "Published 5 pages.",
    "data": {}
}
```

### Dependencies

- **WordPress REST API**: `requests` library for HTTP calls
- **Database**: `memory.get_client_secrets()`, `memory.get_entities()`, `memory.update_entity()`
- **Base64**: For Basic Auth encoding

### Configuration Requirements

- **WordPress Credentials**: Must be set up via `scripts/add_client.py` or `memory.save_client_secrets()`
  - `wp_url`: WordPress REST API endpoint (e.g., `https://site.com/wp-json/wp/v2/posts`)
  - `wp_user`: WordPress username
  - `wp_password`: WordPress application password

### Example Usage

```python
# Triggered by Manager Agent in Phase 5
payload = {
    "task": "publish",
    "user_id": "admin@admin.com",
    "params": {}
}
```

### Error Handling

- **No Credentials**: Returns error if WordPress credentials not found for user
- **No Ready Pages**: Returns "complete" status if no pages ready
- **Publish Failures**: Catches exceptions, logs error, continues with next page
- **Individual Page Failures**: Continues processing other pages

### Key Features

- **Multi-Client Support**: Uses per-user credentials from database
- **Safe Publishing**: Publishes as "draft" first (can be manually reviewed)
- **Status Tracking**: Updates page status to "published" after success
- **Extensible**: Supports multiple targets (WordPress, Vercel/GitHub)
- **Basic Auth**: Uses WordPress application passwords for security

### WordPress REST API Requirements

- WordPress site must have REST API enabled
- User must have application password (not regular password)
- Application password format: `xxxx xxxx xxxx xxxx xxxx xxxx` (spaces included)
- Endpoint: `https://yoursite.com/wp-json/wp/v2/posts`

### Vercel/GitHub Publishing (Placeholder)

The `publish_to_github()` method is a placeholder that:
- Would commit markdown files to GitHub repo
- Vercel would auto-detect commit and rebuild
- Currently returns `True` without implementation
- Requires GitHub API token for full implementation

---

## 9. Twilio Agent

**File**: `backend/agents/twilio_agent.py`  
**Class**: `TwilioAgent`  
**Task Name**: N/A (Standalone Agent)  
**Profile Required**: ❌ No

### Purpose

**Note**: This agent is NOT integrated into the Kernel routing system. It's a standalone background service that polls for new leads and sends SMS notifications via Twilio.

### How It Works

#### Step-by-Step Process

1. **Initialization**
   - Connects to Supabase (legacy database connection)
   - Connects to Twilio using credentials from environment
   - Sets up logger: `Apex.TwilioAgent`

2. **Main Loop** (`run()`)
   - Infinite loop that:
     - Calls `process_new_leads()`
     - Sleeps for 10 seconds
     - Repeats indefinitely
   - Catches all exceptions to prevent loop termination

3. **Lead Processing** (`process_new_leads()`)
   - Queries Supabase `entities` table:
     - Filters: `entity_type == "lead"`
     - Filters: `metadata->>notified` is `false` or null
   - Processes each unnotified lead

4. **SMS Dispatch** (`dispatch_sms()`)
   - **Target Phone Resolution**:
     - Priority A: Check `client_secrets` table (future feature)
     - Priority B: Use `TARGET_PHONE` environment variable
   - **Message Formatting**:
     - Extracts from lead metadata:
       - `name`: `metadata.data.fullName` or "Unknown"
       - `phone`: `metadata.data.phoneNumber` or "Unknown"
       - `source`: `metadata.source` or "Unknown"
     - Formats SMS:
       ```
       🔥 Apex Lead Alert!
       Source: {source}
       Name: {name}
       Phone: {phone}
       ```
   - **SMS Sending**:
     - Uses Twilio Client: `messages.create()`
     - From: `TWILIO_PHONE_NUMBER` env var
     - To: Target phone number
   - **Database Update**:
     - Marks lead as notified: `metadata.notified = True`
     - Updates Supabase entity

### Input/Output

**Note**: This agent doesn't use the standard `AgentInput`/`AgentOutput` pattern. It's a standalone service.

#### Standalone Execution
```python
# Run as standalone script
if __name__ == "__main__":
    agent = TwilioAgent()
    asyncio.run(agent.run())
```

### Dependencies

- **Twilio SDK**: `twilio.rest.Client`
- **Supabase SDK**: `supabase` library (legacy database connection)
- **Environment Variables**:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_PHONE_NUMBER`
  - `TARGET_PHONE` (fallback)

### Configuration Requirements

None (uses environment variables directly)

### Example Usage

```python
# Run as background service
python backend/agents/twilio_agent.py
```

### Error Handling

- **Critical Loop Errors**: Catches exceptions, logs error, continues loop
- **No Target Phone**: Logs warning, skips lead
- **SMS Send Failure**: Logs error, continues with next lead
- **Database Update Failure**: Logs error, continues

### Key Features

- **Background Service**: Runs continuously, polling every 10 seconds
- **Lead Notification**: Sends SMS alerts for new leads
- **Multi-Client Ready**: Designed for per-client phone numbers (future)
- **Resilient**: Never stops running, catches all exceptions
- **Legacy Integration**: Uses Supabase (not SQLite like other agents)

### Integration Status

**Current State**: Not integrated into Kernel routing system
- Doesn't inherit from `BaseAgent`
- Doesn't use `AgentInput`/`AgentOutput`
- Runs as standalone background service
- Uses Supabase instead of SQLite memory manager

**Future Integration**: Could be refactored to:
- Inherit from `BaseAgent`
- Use SQLite memory manager
- Be triggered via Kernel routing
- Support project-based lead filtering

---

## Agent Execution Flow Summary

### Complete Pipeline Flow

```
1. Manager Agent (monitors state)
   ↓
2. Scout Agent (finds locations)
   ↓
3. SEO Keyword Agent (generates keywords)
   ↓
4. SEO Writer Agent (writes pages)
   ↓
5. Media Agent (adds images)
   ↓
6. Utility Agent (adds tools)
   ↓
7. Publisher Agent (publishes to WordPress)
   ↓
8. Leads captured via tools → Saved to database
   ↓
9. Twilio Agent (sends SMS notifications) [Background Service]
```

### Agent Dependencies

- **Onboarding Agent**: Independent (creates profiles)
- **Scout Agent**: Independent (finds locations)
- **Manager Agent**: Depends on all other agents (orchestrates)
- **SEO Keyword Agent**: Depends on Scout (needs anchor locations)
- **SEO Writer Agent**: Depends on SEO Keyword (needs pending keywords)
- **Media Agent**: Depends on SEO Writer (needs page drafts)
- **Utility Agent**: Depends on Media (needs pages with images)
- **Publisher Agent**: Depends on Utility (needs pages with tools)
- **Twilio Agent**: Independent background service (monitors leads)

---

## Environment Variables Reference

### Required for All Agents
- `GOOGLE_API_KEY`: For Gemini AI (Onboarding, SEO Keyword, SEO Writer, Utility)

### Agent-Specific
- `UNSPLASH_ACCESS_KEY`: For Media Agent (optional, has fallback)
- `TWILIO_ACCOUNT_SID`: For Twilio Agent
- `TWILIO_AUTH_TOKEN`: For Twilio Agent
- `TWILIO_PHONE_NUMBER`: F