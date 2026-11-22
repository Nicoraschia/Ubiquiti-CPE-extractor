const FALLBACK = "/equipos";
const BASE = "http://interno.invalid";

/**
 * Destino post-login: solo rutas del mismo sitio. Se resuelve con el mismo parser de URL que
 * usa el navegador, que borra TAB/CR/LF y trata "\" como "/": "/\t/evil" o "/\\evil" serian
 * "//evil", un redirect a otro dominio.
 */
export function safeNext(next: unknown): string {
  if (typeof next !== "string" || !next.startsWith("/")) return FALLBACK;
  let url: URL;
  try {
    url = new URL(next, BASE);
  } catch {
    return FALLBACK;
  }
  if (url.origin !== BASE || /[\t\r\n\\]/.test(next) || next.startsWith("//"))
    return FALLBACK;
  if (url.pathname === "/login") return FALLBACK;
  return url.pathname + url.search + url.hash;
}
