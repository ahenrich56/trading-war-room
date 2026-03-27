import { NextRequest } from "next/server";

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const since = searchParams.get("since") || "";
    const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

    const qs = since ? `?since=${encodeURIComponent(since)}` : "";
    const response = await fetch(`${FASTAPI_URL}/api/v1/alerts${qs}`, { cache: "no-store" });
    const data = await response.json();

    return new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err: any) {
    return new Response(JSON.stringify({ alerts: [], unread: 0, error: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}

export async function POST() {
  try {
    const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const response = await fetch(`${FASTAPI_URL}/api/v1/alerts/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const data = await response.json();
    return new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
