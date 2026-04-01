import { NextRequest } from "next/server";

export const dynamic = 'force-dynamic';
export const maxDuration = 300; // 5 minutes max for intense multi-agent LLM reasoning

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { ticker, timeframe, riskProfile } = body;

    if (!ticker || !timeframe || !riskProfile) {
      return new Response(JSON.stringify({ error: "Missing required fields" }), {
        status: 400,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Proxy the request to the live FastAPI backend
    // Use an environment variable for the VPS IP, default to localhost for local testing
    const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || "https://warroom-api.31-97-128-136.sslip.io";

    const response = await fetch(`${FASTAPI_URL}/api/v1/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ticker,
        timeframe,
        riskProfile,
      }),
    });

    if (!response.ok || !response.body) {
      const errorText = await response.text();
      throw new Error(`FastAPI Error: ${response.status} - ${errorText}`);
    }

    // Return the readable stream directly to the client as an SSE endpoint
    return new Response(response.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
      },
    });

  } catch (err: any) {
    console.error("API Route Proxy Error:", err);
    
    // Fallback error stream so the frontend doesn't crash on connection failure
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`data: [ERROR] {"text": "Proxy connection failed: ${err.message}"}\n\n`));
        controller.close();
      }
    });
    
    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
      },
    });
  }
}
