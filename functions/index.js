const { onDocumentCreated, onDocumentUpdated } = require("firebase-functions/v2/firestore");
const { logger } = require("firebase-functions");
const admin = require("firebase-admin");

admin.initializeApp();

const db = admin.firestore();

function formatAmount(amount) {
  const value = Number(amount || 0);
  if (!Number.isFinite(value)) return String(amount || "0");
  return value.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function env(name, fallback = "") {
  return String(process.env[name] || fallback).trim();
}

async function sendResendEmail({ to, subject, html }) {
  const apiKey = env("RESEND_API_KEY");
  const from = env("EMAIL_FROM");
  if (!apiKey || !from || !to) {
    return { ok: false, error: "RESEND_API_KEY / EMAIL_FROM / recipient missing." };
  }

  try {
    const response = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from,
        to: [to],
        subject,
        html,
      }),
    });
    const body = await response.text();
    if (!response.ok) {
      return { ok: false, error: `HTTP ${response.status}: ${body}` };
    }
    return { ok: true };
  } catch (error) {
    return { ok: false, error: String(error) };
  }
}

async function listOfficerRecipients(namespace) {
  const emails = new Set();
  const snapshot = await db.collection("users").where("role", "==", "credit_officer").get();
  snapshot.forEach((doc) => {
    const payload = doc.data() || {};
    const docNamespace = String(payload.app_namespace || "").trim();
    const email = String(payload.email || "").trim().toLowerCase();
    if (!email) return;
    if (namespace && docNamespace && docNamespace !== namespace) return;
    emails.add(email);
  });
  const fallbackOfficer = env("OFFICER_EMAIL").toLowerCase();
  if (fallbackOfficer) emails.add(fallbackOfficer);
  return Array.from(emails);
}

function buildOfficerHtml(applicationId, data) {
  const submittedOn = new Date().toLocaleString("en-IN");
  return `
  <html><body style="font-family:Arial,sans-serif;background:#ffffff;color:#1f2937;line-height:1.5;">
    <p>Dear Credit Officer,</p>
    <p>A new loan application has been submitted and is awaiting your review.</p>
    <table style="border-collapse:collapse;min-width:480px;">
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Applicant Name</b></td><td style="padding:8px;border:1px solid #d1d5db;">${data.company_name || "-"}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Business Name</b></td><td style="padding:8px;border:1px solid #d1d5db;">${data.business_name || data.company_name || "-"}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Loan Amount</b></td><td style="padding:8px;border:1px solid #d1d5db;">INR ${formatAmount(data.loan_amount)}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Application ID</b></td><td style="padding:8px;border:1px solid #d1d5db;">${applicationId}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Submitted On</b></td><td style="padding:8px;border:1px solid #d1d5db;">${submittedOn}</td></tr>
    </table>
    <p>Please log in to the CreditMind Officer Portal to review the application and uploaded documents.</p>
    <p style="font-size:12px;color:#6b7280;">This is an automated notification from CreditMind. Do not reply to this email.</p>
  </body></html>`;
}

function buildSeekerHtml(data, decision) {
  const normalized = String(decision || "").toLowerCase();
  let accent = "#f59e0b";
  let opening =
    "Your loan application has been reviewed. A conditional decision has been made - please read the officer's remarks carefully and take the required action.";
  if (normalized === "approved") {
    accent = "#16a34a";
    opening = "We are pleased to inform you that your loan application has been reviewed and Approved.";
  } else if (normalized === "rejected") {
    accent = "#dc2626";
    opening =
      "After careful review of your loan application, we regret to inform you that your application has not been approved at this time.";
  }

  const decisionDate = data.decided_at?.toDate ? data.decided_at.toDate().toLocaleString("en-IN") : new Date().toLocaleString("en-IN");
  return `
  <html><body style="font-family:Arial,sans-serif;background:#ffffff;color:#1f2937;line-height:1.5;">
    <div style="border-left:6px solid ${accent};padding:10px 14px;background:#f9fafb;margin-bottom:14px;">
      <b>${normalized.charAt(0).toUpperCase() + normalized.slice(1)} Decision Update</b>
    </div>
    <p>Dear ${data.company_name || "Applicant"},</p>
    <p>${opening}</p>
    <table style="border-collapse:collapse;min-width:520px;">
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Business Name</b></td><td style="padding:8px;border:1px solid #d1d5db;">${data.business_name || data.company_name || "-"}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Loan Amount</b></td><td style="padding:8px;border:1px solid #d1d5db;">INR ${formatAmount(data.loan_amount)}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Decision</b></td><td style="padding:8px;border:1px solid #d1d5db;">${normalized}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Officer Remarks</b></td><td style="padding:8px;border:1px solid #d1d5db;">${data.officer_remarks || "-"}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Decision Date</b></td><td style="padding:8px;border:1px solid #d1d5db;">${decisionDate}</td></tr>
    </table>
    <p style="font-size:12px;color:#6b7280;">This is an automated notification from CreditMind Lending Platform. For queries, contact your branch.</p>
  </body></html>`;
}

exports.notifyOfficerOnApplicationCreate = onDocumentCreated("applications/{appId}", async (event) => {
  const snapshot = event.data;
  if (!snapshot) return;
  const appId = event.params.appId;
  const data = snapshot.data() || {};
  const namespace = String(data.app_namespace || "").trim();

  const recipients = await listOfficerRecipients(namespace);
  if (!recipients.length) {
    await snapshot.ref.set(
      {
        email_log: {
          notification_status: "failed",
          officer_notified_at: admin.firestore.FieldValue.serverTimestamp(),
          last_error: "No officer recipients found.",
          channel: "cloud_function_resend",
        },
      },
      { merge: true },
    );
    return;
  }

  let sentCount = 0;
  let lastError = "";
  const subject = `CreditMind: New Loan Application Received - ${data.business_name || data.company_name || "Business"}`;
  const html = buildOfficerHtml(appId, data);
  for (const recipient of recipients) {
    const result = await sendResendEmail({ to: recipient, subject, html });
    if (result.ok) sentCount += 1;
    else lastError = result.error || "";
  }

  await snapshot.ref.set(
    {
      email_log: {
        notification_status: sentCount > 0 ? "sent" : "failed",
        officer_notified_at: admin.firestore.FieldValue.serverTimestamp(),
        officer_notified_count: sentCount,
        last_error: sentCount > 0 ? "" : lastError,
        channel: "cloud_function_resend",
      },
    },
    { merge: true },
  );
});

exports.notifySeekerOnDecision = onDocumentUpdated("applications/{appId}", async (event) => {
  if (!event.data) return;
  const before = event.data.before.data() || {};
  const after = event.data.after.data() || {};

  const beforeStatus = String(before.status || "").toLowerCase();
  const afterStatus = String(after.status || "").toLowerCase();
  const isDecision = ["approved", "rejected", "conditional"].includes(afterStatus);
  if (!isDecision || beforeStatus === afterStatus) return;

  const seekerEmail = String(after.user_email || "").trim();
  if (!seekerEmail) {
    await event.data.after.ref.set(
      {
        email_log: {
          notification_status: "failed",
          seeker_notified_at: admin.firestore.FieldValue.serverTimestamp(),
          last_error: "Applicant email missing.",
          channel: "cloud_function_resend",
        },
      },
      { merge: true },
    );
    return;
  }

  const subject = `CreditMind: Your Loan Application Decision - ${afterStatus}`;
  const html = buildSeekerHtml(after, afterStatus);
  const result = await sendResendEmail({ to: seekerEmail, subject, html });
  await event.data.after.ref.set(
    {
      email_log: {
        notification_status: result.ok ? "sent" : "failed",
        seeker_notified_at: admin.firestore.FieldValue.serverTimestamp(),
        last_error: result.ok ? "" : result.error || "Unknown send error",
        channel: "cloud_function_resend",
      },
    },
    { merge: true },
  );

  if (!result.ok) {
    logger.error("Decision email failed", { appId: event.params.appId, error: result.error });
  }
});
