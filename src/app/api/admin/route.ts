import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || "https://warroom-api.31-97-128-136.sslip.io";
const ADMIN_KEY = process.env.ADMIN_KEY || "warroom-admin-2026";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const action = searchParams.get("action") || "dashboard";
    const clientKey = searchParams.get("key") || "";

    if (clientKey !== ADMIN_KEY) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (action === "dashboard") {
      const res = await fetch(`${FASTAPI_URL}/api/v1/admin/dashboard?key=${ADMIN_KEY}`);
      const data = await res.json();
      return new Response(JSON.stringify(data), {
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify({ error: "Unknown action" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const clientKey = body.key || "";

    if (clientKey !== ADMIN_KEY) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      });
    }

    const action = body.action || "";

    if (action === "retrain") {
      const res = await fetch(`${FASTAPI_URL}/api/v1/admin/retrain?key=${ADMIN_KEY}`, {
        method: "POST",
      });
      const data = await res.json();
      return new Response(JSON.stringify(data), {
        headers: { "Content-Type": "application/json" },
      });
    }

    if (action === "clear-db") {
      const res = await fetch(`${FASTAPI_URL}/api/v1/admin/clear-db?key=${ADMIN_KEY}&table=${body.table || "all"}`, {
        method: "POST",
      });
      const data = await res.json();
      return new Response(JSON.stringify(data), {
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify({ error: "Unknown action" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
