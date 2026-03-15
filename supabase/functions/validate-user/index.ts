import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SLACK_TOKEN = Deno.env.get("SLACK_BOT_TOKEN")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { email, schedule_hour = 15 } = await req.json();

    if (!email || !email.includes("@")) {
      return new Response(JSON.stringify({ error: "Invalid email" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Look up user in Slack
    const slackResp = await fetch("https://slack.com/api/users.lookupByEmail", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${SLACK_TOKEN}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: `email=${encodeURIComponent(email)}`,
    });

    const slackData = await slackResp.json();

    if (!slackData.ok) {
      return new Response(
        JSON.stringify({ error: `No Slack user found for ${email}` }),
        {
          status: 404,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    const slackUserId = slackData.user.id;
    const profile = slackData.user.profile || {};
    const displayName =
      profile.display_name || profile.real_name || email.split("@")[0];

    // Save to Supabase
    const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

    const { error: dbError } = await supabase.from("users").upsert(
      {
        email: email.toLowerCase(),
        slack_user_id: slackUserId,
        display_name: displayName,
        schedule_hour,
        active: true,
      },
      { onConflict: "email" }
    );

    if (dbError) {
      throw new Error(`Database error: ${dbError.message}`);
    }

    return new Response(
      JSON.stringify({
        ok: true,
        email: email.toLowerCase(),
        slack_user_id: slackUserId,
        display_name: displayName,
        schedule_hour,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
