export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const FASTAPI_URL = process.env.NEXT_PUBLIC_API_URL || "https://warroom-api.31-97-128-136.sslip.io";
    const response = await fetch(`${FASTAPI_URL}/api/v1/market-overview`, { cache: "no-store" });
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
