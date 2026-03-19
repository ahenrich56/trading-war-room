import { NextRequest } from "next/server";
import { spawn } from "child_process";
import path from "path";

export const dynamic = 'force-dynamic';
export const maxDuration = 180; // 3 minutes max

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

    // Determine the path to the Python script
    const scriptPath = path.join(process.cwd(), "engine", "analyze.py");

    const encoder = new TextEncoder();

    const stream = new ReadableStream({
      start(controller) {
        // Spawn the python process
        // In a real environment, you might need to point this to a specific python executable
        // e.g., representing the 'tradingagents' conda env if the real repo was used.
        const pythonProcess = spawn("python", [
          scriptPath,
          "--ticker", ticker,
          "--timeframe", timeframe,
          "--risk_profile", riskProfile
        ]);

        pythonProcess.stdout.on("data", (data) => {
          // The data can be a chunk containing multiple lines
          const lines = data.toString().split("\n");
          for (const line of lines) {
            if (line.trim()) {
              // Write each line as a standard Server-Sent Event
              controller.enqueue(encoder.encode(`data: ${line}\n\n`));
            }
          }
        });

        pythonProcess.stderr.on("data", (data) => {
          console.error(`Python Error: ${data.toString()}`);
        });

        pythonProcess.on("close", (code) => {
          console.log(`Python process exited with code ${code}`);
          controller.close();
        });

        pythonProcess.on("error", (err) => {
          console.error("Failed to start subprocess.", err);
          controller.enqueue(encoder.encode(`data: [ERROR] {"text": "Process failed: ${err.message}"}\n\n`));
          controller.close();
        });
      }
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
      },
    });

  } catch (err) {
    console.error("API Route Error:", err);
    return new Response(JSON.stringify({ error: "Internal Server Error" }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}
