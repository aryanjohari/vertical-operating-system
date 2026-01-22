# Twilio & Environment Configuration Guide

## Environment Variables (.env)

Add these to your `.env` file:

```bash
# ============================================================
# TWILIO CONFIGURATION (Bridge Call Pipeline)
# ============================================================
# Get these from: https://console.twilio.com/
# 1. Account SID: Dashboard → Account Info
# 2. Auth Token: Dashboard → Account Info (click to reveal)
# 3. Phone Number: Phone Numbers → Manage → Active Numbers (your +64 9... number)

TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+6491234567

# ============================================================
# NGROK CONFIGURATION (For Local Testing)
# ============================================================
# Get this from: https://dashboard.ngrok.com/get-started/your-authtoken
# After running: ngrok http 8000
# Copy the "Forwarding" URL (e.g., https://abc123.ngrok.io)
# IMPORTANT: Update this every time you restart ngrok (URL changes on free tier)

NGROK_URL=https://your-ngrok-url.ngrok.io

# ============================================================
# PRODUCTION API URL (Optional - for production deployment)
# ============================================================
# Only set this if you're deploying to production
# Leave empty if using NGROK_URL for testing

NEXT_PUBLIC_API_URL=

# ============================================================
# DEFAULT PROJECT (Optional - for voice router fallback)
# ============================================================
# Used by /api/voice/incoming endpoint if project_id not in query params

DEFAULT_PROJECT_ID=specialist_support_services

# ============================================================
# GOOGLE API KEY (For Gemini Transcription)
# ============================================================
# Get this from: https://aistudio.google.com/app/apikey
# Required for call transcription (better quality, lower cost than Twilio)
# Uses the same GOOGLE_API_KEY as your LLM gateway
# Note: Already set if you're using Gemini for other features

GOOGLE_API_KEY=your_google_api_key_here
```

## Twilio Console Configuration

### 1. Enable Call Recording

1. Go to **Phone Numbers** → **Manage** → **Active Numbers**
2. Click your Twilio number (+64 9...)
3. Scroll to **Voice & Fax** section
4. Under **Record Calls**, select:
   - ✅ **Record calls** (enabled)
   - **Recording Status Callback URL**: `https://your-ngrok-url.ngrok.io/api/voice/recording-status`
   - **Recording Status Callback Method**: POST

### 2. Transcription (Using Google Gemini)

**Note**: We use Google Gemini for transcription (better quality, lower cost).
- Twilio auto-transcription is **NOT** needed
- Transcription happens automatically when call completes
- Recordings are automatically deleted after transcription to minimize storage costs
- Uses the same `GOOGLE_API_KEY` as your LLM gateway

### 3. Configure Webhook URLs (For Inbound Calls)

1. In **Voice & Fax** section:
   - **A CALL COMES IN**: `https://your-ngrok-url.ngrok.io/api/voice/incoming?project_id=specialist_support_services`
   - **HTTP Method**: POST

### 4. Verify Webhook URLs

After setting up Ngrok, test your webhooks:
- Status Callback: `https://your-ngrok-url.ngrok.io/api/voice/status`
- Recording Status: `https://your-ngrok-url.ngrok.io/api/voice/recording-status`

## Testing Checklist

- [ ] Twilio credentials added to `.env`
- [ ] Google API key added to `.env` (for Gemini transcription - same as LLM gateway)
- [ ] Ngrok tunnel running (`ngrok http 8000`)
- [ ] `NGROK_URL` updated in `.env`
- [ ] Call recording enabled in Twilio Console
- [ ] Webhook URLs configured in Twilio Console
- [ ] Project DNA has `destination_phone` configured
- [ ] Backend server running on port 8000

## Project DNA Configuration

Ensure your project DNA (`data/profiles/specialist_support_services/dna.generated.yaml` or `dna.custom.yaml`) has:

```yaml
modules:
  lead_gen:
    enabled: true
    sales_bridge:
      destination_phone: "+6491234567"  # Your phone number
      whisper_text: "New Lead. Press 1 to connect."
      sms_alert_template: "New Lead: [Name] from [Source]"
```

## Flow Summary

1. **Form Submission** → `/api/webhooks/wordpress?project_id=...` → Lead created → Auto-triggers bridge call
2. **Bridge Call** → SalesAgent → Twilio calls boss → Boss presses 1 → Connects to customer
3. **Call Ends** → Status callback → Finds lead → Downloads recording → Transcribes with Whisper → Deletes recording → Updates lead entity
4. **Lead Updated** → Status: "called", Transcription saved, Gemini analysis saved (summary, key points, sentiment, etc.)

## Troubleshooting

### Calls not recording?
- Check Twilio Console → Phone Numbers → Your number → Record Calls is enabled
- Verify `NGROK_URL` is correct and accessible
- Check backend logs for status callback errors

### Transcription not working?
- Verify `GOOGLE_API_KEY` is set in `.env` (same key used for LLM gateway)
- Check backend logs for Gemini API errors
- Ensure recording URL is accessible (may require Twilio authentication)
- Transcription happens automatically when call completes (via status callback)
- Verify Gemini model supports audio (gemini-2.5-flash or gemini-1.5-pro)

### Leads not showing in dashboard?
- Verify form is POSTing to `/api/webhooks/wordpress` (not `/api/leads`)
- Check `project_id` matches your project
- Check backend logs for webhook errors

### Status callback not updating leads?
- Verify `lead_id` and `project_id` are in status callback URL query params
- Check that `call_sid` is stored in lead metadata when call is initiated
- Review backend logs for lead lookup errors
