import type { SVGProps } from "react";

// Iconos de trazo fino, decorativos: el nombre accesible lo da el enlace o boton que los contiene.
function Icon({ children, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export const IconDevices = () => (
  <Icon>
    <path d="M4 6h16M4 12h16M4 18h10" />
  </Icon>
);
export const IconAp = () => (
  <Icon>
    <path d="M12 20v-8M8.5 8.5a5 5 0 0 1 7 0M5.6 5.6a9 9 0 0 1 12.8 0" />
    <circle cx="12" cy="12" r="1.2" />
  </Icon>
);
export const IconRouter = () => (
  <Icon>
    <rect x="3" y="13" width="18" height="6" rx="1" />
    <path d="M7 16h.01M11 16h.01M8 13 6 7M16 13l2-6" />
  </Icon>
);
export const IconScan = () => (
  <Icon>
    <path d="M20 12a8 8 0 1 1-3-6.2M20 4v5h-5" />
  </Icon>
);
export const IconSubnet = () => (
  <Icon>
    <rect x="4" y="4" width="6" height="6" />
    <rect x="14" y="4" width="6" height="6" />
    <rect x="9" y="14" width="6" height="6" />
    <path d="M7 10v2h10v-2M12 12v2" />
  </Icon>
);
export const IconUsers = () => (
  <Icon>
    <circle cx="9" cy="8" r="3.2" />
    <path d="M3 20a6 6 0 0 1 12 0M16 4.5a3.2 3.2 0 0 1 0 6.4M21 20a6 6 0 0 0-4-5.6" />
  </Icon>
);
export const IconAudit = () => (
  <Icon>
    <path d="M7 3h8l4 4v14H7z" />
    <path d="M15 3v4h4M10 12h6M10 16h6" />
  </Icon>
);
export const IconSearch = () => (
  <Icon width="16" height="16" strokeWidth="1.8">
    <circle cx="11" cy="11" r="6.5" />
    <path d="m20 20-4-4" />
  </Icon>
);
