import spec from "../../../web/src/lib/docs/public-openapi.json";

export function GET() {
  return Response.json(spec);
}
