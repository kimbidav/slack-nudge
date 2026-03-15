import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SLACK_TOKEN = Deno.env.get("SLACK_BOT_TOKEN")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const NUDGE_DAYS = parseInt(Deno.env.get("NUDGE_DAYS") || "3");
const LOOKBACK_DAYS = parseInt(Deno.env.get("LOOKBACK_DAYS") || "60");

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// ── Slack API helpers ───────────────────────────────────────────────────────

async function slackApi(method: string, params: Record<string, string> = {}) {
  const url = new URL(`https://slack.com/api/${method}`);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);

  const resp = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${SLACK_TOKEN}` },
  });
  const data = await resp.json();
  if (!data.ok) throw new Error(`Slack API ${method}: ${data.error}`);
  return data;
}

async function slackPost(method: string, body: Record<string, string>) {
  const resp = await fetch(`https://slack.com/api/${method}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${SLACK_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return resp.json();
}

async function getConnectChannels(userId: string) {
  const channels: any[] = [];
  let cursor = "";

  do {
    const params: Record<string, string> = {
      user: userId,
      types: "public_channel,private_channel",
      limit: "200",
    };
    if (cursor) params.cursor = cursor;

    const data = await slackApi("users.conversations", params);
    for (const ch of data.channels || []) {
      if (ch.is_ext_shared) channels.push(ch);
    }
    cursor = data.response_metadata?.next_cursor || "";
  } while (cursor);

  return channels;
}

async function getChannelMessages(channelId: string, oldestTs: string) {
  const messages: any[] = [];
  let cursor = "";

  do {
    const params: Record<string, string> = {
      channel: channelId,
      oldest: oldestTs,
      limit: "200",
    };
    if (cursor) params.cursor = cursor;

    try {
      const data = await slackApi("conversations.history", params);
      messages.push(...(data.messages || []));
      cursor = data.response_metadata?.next_cursor || "";
    } catch (e) {
      // Rate limit — wait and retry
      if (String(e).includes("ratelimited")) {
        await new Promise((r) => setTimeout(r, 5000));
        continue;
      }
      console.error(`Error fetching ${channelId}: ${e}`);
      break;
    }
  } while (cursor);

  return messages;
}

async function getWorkspaceDomain(): Promise<string> {
  const data = await slackApi("team.info");
  return data.team?.domain ? `${data.team.domain}.slack.com` : "slack.com";
}

// ── LinkedIn extraction ─────────────────────────────────────────────────────

const LINKEDIN_RE =
  /https?:\/\/(?:www\.)?linkedin\.com\/in\/[a-zA-Z0-9_-]+\/?/gi;

function extractLinkedInUrls(text: string): string[] {
  return [...text.matchAll(LINKEDIN_RE)].map((m) => m[0]);
}

// ── Status inference from emoji reactions ────────────────────────────────────

const CLOSED_EMOJIS = new Set(["no_entry_sign", "no_entry", "x", "octagonal_sign"]);
const IN_PROCESS_EMOJIS = new Set(["white_check_mark", "heavy_check_mark", "ballot_box_with_check"]);

function inferStatus(msg: any): "CLOSED" | "IN_PROCESS_EXPLICIT" | "IN_PROCESS_UNCLEAR" {
  const reactions: any[] = msg.reactions || [];
  for (const r of reactions) {
    if (CLOSED_EMOJIS.has(r.name)) return "CLOSED";
  }
  for (const r of reactions) {
    if (IN_PROCESS_EMOJIS.has(r.name)) return "IN_PROCESS_EXPLICIT";
  }
  return "IN_PROCESS_UNCLEAR";
}

// ── Nudge tracker (using Supabase) ──────────────────────────────────────────

async function getRecentNudges(
  supabase: any,
  userEmail: string
): Promise<Set<string>> {
  const since = new Date(Date.now() - NUDGE_DAYS * 24 * 60 * 60 * 1000).toISOString();
  const { data } = await supabase
    .from("nudge_runs")
    .select("details")
    .eq("user_email", userEmail)
    .gte("ran_at", since)
    .order("ran_at", { ascending: false })
    .limit(5);

  const nudged = new Set<string>();
  for (const run of data || []) {
    for (const sub of run.details?.submissions_needing_nudge || []) {
      // Track by channel+candidate to avoid re-nudging
      nudged.add(`${sub.channel_name}:${sub.candidate_name}`);
    }
  }
  return nudged;
}

// ── Main handler ────────────────────────────────────────────────────────────

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { email } = await req.json();
    if (!email) {
      return new Response(JSON.stringify({ error: "email required" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

    // Load user
    const { data: user } = await supabase
      .from("users")
      .select("*")
      .eq("email", email.toLowerCase())
      .single();

    if (!user) {
      return new Response(JSON.stringify({ error: "User not registered" }), {
        status: 404,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const userId = user.slack_user_id;
    console.log(`[NUDGE] Starting scan for ${email} (${userId})`);

    // Get Slack Connect channels
    const channels = await getConnectChannels(userId);
    console.log(`[NUDGE] Found ${channels.length} Slack Connect channels`);

    // Scan for submissions
    const oldestTs = String(
      Math.floor(Date.now() / 1000) - LOOKBACK_DAYS * 86400
    );

    const submissions: any[] = [];

    for (const ch of channels) {
      const messages = await getChannelMessages(ch.id, oldestTs);

      for (const msg of messages) {
        // Only top-level messages from this user
        if (msg.user !== userId) continue;
        if (msg.thread_ts && msg.thread_ts !== msg.ts) continue;

        const linkedinUrls = extractLinkedInUrls(msg.text || "");
        if (linkedinUrls.length === 0) continue;

        const status = inferStatus(msg);
        const submittedAt = parseFloat(msg.ts);
        const daysSince = Math.floor(
          (Date.now() / 1000 - submittedAt) / 86400
        );

        // Extract candidate name (text before the LinkedIn URL)
        const text = msg.text || "";
        const urlIndex = text.indexOf("linkedin.com");
        const beforeUrl = text.substring(0, urlIndex).trim();
        const candidateName =
          beforeUrl.split("\n").pop()?.trim() || "Unknown candidate";

        submissions.push({
          candidate_name: candidateName,
          channel_name: ch.name,
          channel_id: ch.id,
          status,
          days_since_submission: daysSince,
          linkedin_url: linkedinUrls[0],
          ts: msg.ts,
        });
      }
    }

    console.log(`[NUDGE] Found ${submissions.length} total submissions`);

    // Find submissions needing nudge
    const recentNudges = await getRecentNudges(supabase, email);

    const needingNudge = submissions.filter((s) => {
      if (s.status !== "IN_PROCESS_UNCLEAR") return false;
      if (s.days_since_submission < NUDGE_DAYS) return false;
      const key = `${s.channel_name}:${s.candidate_name}`;
      if (recentNudges.has(key)) return false;
      return true;
    });

    console.log(`[NUDGE] ${needingNudge.length} submissions need nudge`);

    // Send Slack DM summary
    if (needingNudge.length > 0) {
      const domain = await getWorkspaceDomain();

      const dmLines = [
        `*Nudge Summary*: ${needingNudge.length} candidates need follow-up\n`,
      ];
      for (const s of needingNudge) {
        const tsForUrl = s.ts.replace(".", "");
        const threadUrl = `https://${domain}/archives/${s.channel_id}/p${tsForUrl}`;
        dmLines.push(
          `• <${threadUrl}|${s.candidate_name}> in #${s.channel_name} (${s.days_since_submission} days)`
        );
      }

      await slackPost("chat.postMessage", {
        channel: userId,
        text: dmLines.join("\n"),
      });
      console.log(`[NUDGE] Sent DM to ${email}`);
    }

    // Save run to DB
    const results = {
      submissions_checked: submissions.length,
      nudges_needed: needingNudge.length,
      nudges_sent: needingNudge.length,
      submissions_needing_nudge: needingNudge.map((s) => ({
        candidate_name: s.candidate_name,
        channel_name: s.channel_name,
        days_since_submission: s.days_since_submission,
      })),
    };

    await supabase.from("nudge_runs").insert({
      user_email: email.toLowerCase(),
      ran_at: new Date().toISOString(),
      submissions_checked: results.submissions_checked,
      nudges_needed: results.nudges_needed,
      nudges_sent: results.nudges_sent,
      details: results,
    });

    return new Response(JSON.stringify({ ok: true, ...results }), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error(`[NUDGE] Error: ${err}`);
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
