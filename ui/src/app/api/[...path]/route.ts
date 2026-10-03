import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8741";
const REVIEW_API_KEY = process.env.REVIEW_API_KEY?.trim();

async function proxy(req: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const { path } = await ctx.params;
  const target = `${API_BASE_URL}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers: Record<string, string> = { accept: "application/json" };
  if (REVIEW_API_KEY) {
    headers["x-api-key"] = REVIEW_API_KEY;
  }
  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      cache: "no-store",
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json(
      { detail: `Review API is unreachable at ${API_BASE_URL}. Start it with: uvicorn review_assistant.api:app --port 8741` },
      { status: 502 },
    );
  }
}

export { proxy as GET, proxy as POST };
