// Supabase Edge Function: email-notify
// Expects:
// {
//   "event_type": "new_application" | "decision_update",
//   "payload": { ... }
// }
// Requires secrets:
// - RESEND_API_KEY
// - EMAIL_FROM
// - OFFICER_EMAIL (optional fallback)

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
};

function formatAmount(amount: unknown): string {
  const n = Number(amount || 0);
  if (!Number.isFinite(n)) return String(amount ?? "0");
  return n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

async function sendResendEmail(to: string, subject: string, html: string): Promise<{ ok: boolean; error?: string }> {
  const apiKey = Deno.env.get("RESEND_API_KEY")?.trim() || "";
  const from = Deno.env.get("EMAIL_FROM")?.trim() || "";
  if (!apiKey || !from || !to) return { ok: false, error: "Missing RESEND_API_KEY/EMAIL_FROM/recipient." };

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
  if (!response.ok) {
    return { ok: false, error: `Resend HTTP ${response.status}: ${await response.text()}` };
  }
  return { ok: true };
}

function officerHtml(payload: Record<string, unknown>): string {
  return `
  <html><body style="font-family:Arial,sans-serif;background:#ffffff;color:#1f2937;line-height:1.5;">
    <p>Dear Credit Officer,</p>
    <p>A new loan application has been submitted and is awaiting your review.</p>
    <table style="border-collapse:collapse;min-width:480px;">
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Applicant Name</b></td><td style="padding:8px;border:1px solid #d1d5db;">${String(payload.applicant_name || "-")}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Business Name</b></td><td style="padding:8px;border:1px solid #d1d5db;">${String(payload.business_name || "-")}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Loan Amount</b></td><td style="padding:8px;border:1px solid #d1d5db;">INR ${formatAmount(payload.loan_amount)}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Application ID</b></td><td style="padding:8px;border:1px solid #d1d5db;">${String(payload.application_id || "-")}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Submitted On</b></td><td style="padding:8px;border:1px solid #d1d5db;">${new Date().toLocaleString("en-IN")}</td></tr>
    </table>
    <p>Please log in to the CreditMind Officer Portal to review the application and uploaded documents.</p>
    <p style="font-size:12px;color:#6b7280;">This is an automated notification from CreditMind. Do not reply to this email.</p>
  </body></html>`;
}

function seekerHtml(payload: Record<string, unknown>): string {
  const decision = String(payload.decision || "").toLowerCase();
  let accent = "#f59e0b";
  let opening =
    "Your loan application has been reviewed. A conditional decision has been made - please read the officer's remarks carefully and take the required action.";
  if (decision === "approved") {
    accent = "#16a34a";
    opening = "We are pleased to inform you that your loan application has been reviewed and Approved.";
  } else if (decision === "rejected") {
    accent = "#dc2626";
    opening =
      "After careful review of your loan application, we regret to inform you that your application has not been approved at this time.";
  }

  return `
  <html><body style="font-family:Arial,sans-serif;background:#ffffff;color:#1f2937;line-height:1.5;">
    <div style="border-left:6px solid ${accent};padding:10px 14px;background:#f9fafb;margin-bottom:14px;">
      <b>${decision || "decision"} Decision Update</b>
    </div>
    <p>Dear ${String(payload.applicant_name || "Applicant")},</p>
    <p>${opening}</p>
    <table style="border-collapse:collapse;min-width:520px;">
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Business Name</b></td><td style="padding:8px;border:1px solid #d1d5db;">${String(payload.business_name || "-")}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Loan Amount</b></td><td style="padding:8px;border:1px solid #d1d5db;">INR ${formatAmount(payload.loan_amount)}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Decision</b></td><td style="padding:8px;border:1px solid #d1d5db;">${decision}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Officer Remarks</b></td><td style="padding:8px;border:1px solid #d1d5db;">${String(payload.officer_remarks || "-")}</td></tr>
      <tr><td style="padding:8px;border:1px solid #d1d5db;"><b>Decision Date</b></td><td style="padding:8px;border:1px solid #d1d5db;">${String(payload.decided_at || new Date().toLocaleString("en-IN"))}</td></tr>
    </table>
    <p style="font-size:12px;color:#6b7280;">This is an automated notification from CreditMind Lending Platform. For queries, contact your branch.</p>
  </body></html>`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  try {
    const { event_type, payload } = await req.json();
    const eventType = String(event_type || "").trim();
    const data = (payload || {}) as Record<string, unknown>;

    if (eventType === "new_application") {
      const recipients = new Set<string>();
      const list = Array.isArray(data.officer_recipients) ? data.officer_recipients : [];
      for (const item of list) {
        const email = String(item || "").trim().toLowerCase();
        if (email) recipients.add(email);
      }
      const fallback = String(data.officer_email_fallback || Deno.env.get("OFFICER_EMAIL") || "").trim().toLowerCase();
      if (fallback) recipients.add(fallback);
      if (!recipients.size) {
        return new Response(JSON.stringify({ ok: false, sent_count: 0, error: "No officer recipients found." }), {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 200,
        });
      }

      let sentCount = 0;
      let lastError = "";
      const subject = `CreditMind: New Loan Application Received - ${String(data.business_name || "Business")}`;
      const html = officerHtml(data);
      for (const recipient of recipients) {
        const result = await sendResendEmail(recipient, subject, html);
        if (result.ok) sentCount += 1;
        else lastError = result.error || "";
      }

      return new Response(
        JSON.stringify({
          ok: sentCount > 0,
          sent_count: sentCount,
          error: sentCount > 0 ? "" : lastError,
        }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 },
      );
    }

    if (eventType === "decision_update") {
      const seekerEmail = String(data.seeker_email || "").trim();
      if (!seekerEmail) {
        return new Response(JSON.stringify({ ok: false, sent_count: 0, error: "Applicant email missing." }), {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
          status: 200,
        });
      }
      const decision = String(data.decision || "decision");
      const subject = `CreditMind: Your Loan Application Decision - ${decision}`;
      const html = seekerHtml(data);
      const result = await sendResendEmail(seekerEmail, subject, html);
      return new Response(
        JSON.stringify({
          ok: result.ok,
          sent_count: result.ok ? 1 : 0,
          error: result.error || "",
        }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 },
      );
    }

    return new Response(JSON.stringify({ ok: false, sent_count: 0, error: "Unsupported event_type." }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 400,
    });
  } catch (error) {
    return new Response(JSON.stringify({ ok: false, sent_count: 0, error: String(error) }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 500,
    });
  }
});
