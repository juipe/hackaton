/**
 * The single declaration of every API shape.
 *
 * This mirrors section 7 of docs/contract.md. Money is always an integer number of
 * minor units (cents) in a field ending in `_cents` — no decimal money crosses the
 * wire, so nothing here needs float-safe parsing. Use `src/lib/money.ts` to render it.
 */
export {};
