/** Liveness probe for the function runtime itself. If this answers and a
 *  sibling endpoint 500s, the sibling's failure is in its own imports or
 *  logic — not in the api/ directory wiring. */
export default function handler(_req: unknown, res: {
  setHeader: (k: string, v: string) => void;
  status: (n: number) => { json: (b: unknown) => void };
}) {
  res.setHeader("cache-control", "no-store");
  res.status(200).json({ ok: true, runtime: "vercel-node" });
}
