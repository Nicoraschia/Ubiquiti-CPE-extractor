/** Destino post-login: solo rutas internas. Evita el open redirect con "//evil.com" o "/\\evil.com". */
export function safeNext(next: unknown): string {
  if (
    typeof next !== "string" ||
    !next.startsWith("/") ||
    next.startsWith("//") ||
    next.startsWith("/\\")
  ) {
    return "/equipos";
  }
  if (next === "/login" || next.startsWith("/login?")) return "/equipos";
  return next;
}
