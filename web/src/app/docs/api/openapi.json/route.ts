import spec from "@/lib/docs/public-openapi.json";

export function GET() {
  return Response.json(spec, { headers: { "cache-control": "public, max-age=300" } });
}
