// `__Host-` obliga a Secure, Path=/ y sin Domain: el navegador rechaza la cookie si alguien
// intenta fijarla desde otro subdominio o por HTTP.
export const SESSION_COOKIE = "__Host-cpe_session";
export const SESSION_MAX_AGE_S = 12 * 60 * 60; // igual que SESSION_MAX en la API
