# Supabase Email Notifications (Free-tier friendly)

This project now supports email notifications through a Supabase Edge Function (no Firebase Blaze required).

## Files added

- `supabase/functions/email-notify/index.ts`
- `supabase_notifications.py`

## What it does

From Streamlit:
- On new application -> calls Supabase Edge Function event `new_application`
- On officer decision -> calls Supabase Edge Function event `decision_update`

Edge Function sends emails via Resend and returns `{ ok, sent_count, error }`.
Streamlit writes `email_log` in Firestore accordingly.

## Required `.env` in Streamlit app

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_NOTIFY_FUNCTION=email-notify` (optional; default is `email-notify`)
- `USE_SUPABASE_EMAIL_NOTIFICATIONS=true`

## Required secrets in Supabase Edge Function

Set in Supabase:

- `RESEND_API_KEY`
- `EMAIL_FROM`
- `OFFICER_EMAIL` (optional fallback)

## Deploy Edge Function

```bash
supabase functions deploy email-notify
```

Then set secrets:

```bash
supabase secrets set RESEND_API_KEY=... EMAIL_FROM=... OFFICER_EMAIL=...
```
