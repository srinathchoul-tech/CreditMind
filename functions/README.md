# CreditMind Cloud Email Notifications (Firebase Functions + Resend)

This folder contains server-side email triggers so notifications are sent from Firebase Cloud Functions (not your local machine).

## What it does

- `notifyOfficerOnApplicationCreate`:
  - Trigger: new document in `applications/{appId}`
  - Sends "new application" email to all credit officers in `users` collection (role = `credit_officer`) and optional `OFFICER_EMAIL` fallback.
  - Writes audit info to `applications/{appId}.email_log`.

- `notifySeekerOnDecision`:
  - Trigger: updates to `applications/{appId}`
  - When status changes to `approved | rejected | conditional`, sends decision email to `user_email`.
  - Writes audit info to `applications/{appId}.email_log`.

## Required environment variables (Functions runtime)

Set these in Firebase Functions config/environment:

- `RESEND_API_KEY`
- `EMAIL_FROM`
- `OFFICER_EMAIL` (optional fallback recipient)

## Deploy

From project root:

```powershell
cd functions
npm install
```

Then from repo root (after Firebase CLI login/init):

```powershell
firebase deploy --only functions
```

## Notes

- Streamlit app is configured for cloud notifications when:
  - `USE_CLOUD_EMAIL_NOTIFICATIONS=true` in `.env`
- In that mode, local SMTP send attempts are skipped to avoid local network blocks.
