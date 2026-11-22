import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Imagen Docker minima: server.js + solo las dependencias usadas.
  output: "standalone",
  poweredByHeader: false,
  // Sin cacheComponents: el CSP con nonce exige render por request, y toda pagina
  // depende de la sesion. Un shell prerenderizado no tendria el nonce.
  experimental: {
    serverActions: { bodySizeLimit: "64kb" },
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
