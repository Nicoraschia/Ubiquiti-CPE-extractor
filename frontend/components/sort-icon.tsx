/** Flechas de orden. Decorativas: el sentido lo comunica aria-sort en el <th>, que tambien las pinta. */
export function SortIcon() {
  return (
    <svg
      className="sort-icon"
      viewBox="0 0 8 12"
      width="8"
      height="12"
      aria-hidden="true"
    >
      <path className="up" d="M4 0 8 5H0z" />
      <path className="down" d="M4 12 0 7h8z" />
    </svg>
  );
}
