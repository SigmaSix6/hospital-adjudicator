import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8741";

async function proxy(req: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const { path } = await ctx.params;
  const target = `${API_BASE_URL}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers: { accept: "application/json" },
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
