import { NextRequest } from "next/server";

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  try {
    const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || "https://warroom-api.31-97-128-136.sslip.io";
    const response = await fetch(`${FASTAPI_URL}/api/v1/ml-stats`);
    const data = await response.json();

    return new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err: any) {
    return new Response(JSON.stringify({ status: "error", message: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
