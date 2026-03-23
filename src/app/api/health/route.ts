import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    
    // Quick timeout for health check
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);
    
    const res = await fetch(`${FASTAPI_URL}/health`, {
      signal: controller.signal,
      headers: { "Content-Type": "application/json" }
    });
    
    clearTimeout(timeoutId);
    
    if (!res.ok) {
      return NextResponse.json({ status: "error", message: `HTTP ${res.status}` }, { status: 502 });
    }
    
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ status: "error", message: error.message }, { status: 503 });
  }
}
