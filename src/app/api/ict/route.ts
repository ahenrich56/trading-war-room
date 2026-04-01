import { NextRequest } from "next/server";

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || "https://warroom-api.31-97-128-136.sslip.io";

    const response = await fetch(`${FASTAPI_URL}/api/v1/ict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    return new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err.message, ict: {} }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
