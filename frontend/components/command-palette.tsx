"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, useTransition } from "react";

import { search, type SearchHit } from "@/app/(app)/search-action";

import { IconSearch } from "./icons";
import { SignalMeter } from "./signal-meter";

function isTyping(el: EventTarget | null): boolean {
  return (
    el instanceof HTMLElement &&
    (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName))
  );
}

/**
 * Busqueda global: "/" o Cmd/Ctrl+K desde cualquier pantalla. <dialog> nativo modal:
 * el navegador da foco atrapado, Esc, backdrop y devuelve el foco al cerrar.
 */
export function CommandPalette() {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const listId = useId();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [active, setActive] = useState(0);
  const [pending, startTransition] = useTransition();
  const seq = useRef(0);

  // React aplica autoFocus al montar, no como atributo: el dialogo no lo veria al abrirse.
  function open() {
    dialog.current?.showModal();
    input.current?.focus();
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const cmdK = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k";
      if (cmdK || (e.key === "/" && !isTyping(e.target))) {
        e.preventDefault();
        open();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) return;
    // Debounce + descarta respuestas viejas si el usuario siguio escribiendo.
    const id = ++seq.current;
    const t = setTimeout(() => {
      startTransition(async () => {
        const result = await search(term);
        if (id === seq.current) {
          setHits(result);
          setActive(0);
        }
      });
    }, 180);
    return () => clearTimeout(t);
  }, [q]);

  const shown = q.trim().length < 2 ? [] : hits;

  function go(hit: SearchHit | undefined) {
    if (!hit) {
      if (q.trim()) router.push(`/equipos?q=${encodeURIComponent(q.trim())}`);
    } else {
      router.push(`/equipos/${hit.mac}`);
    }
    dialog.current?.close();
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.nativeEvent.isComposing) return; // IME: Enter confirma el texto, no navega
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, shown.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(shown[active]);
    }
  }

  const optionId = (i: number) => `${listId}-${i}`;

  return (
    <>
      <button
        type="button"
        onClick={open}
        className="flex h-8 w-full max-w-[520px] items-center gap-2 rounded-md border border-border bg-bg px-2.5 text-left text-faint transition-colors duration-150 hover:border-border-strong"
        aria-keyshortcuts="/ Control+K Meta+K"
      >
        <IconSearch />
        <span className="flex-1 truncate">
          Buscar MAC, IP, cliente, router...
        </span>
        <kbd>/</kbd>
      </button>

      <dialog
        ref={dialog}
        aria-label="Busqueda global"
        // closedby es mejora progresiva: sin soporte, Esc igual cierra.
        {...{ closedby: "any" }}
        onClose={() => {
          setQ("");
          setHits([]);
        }}
        className="mx-auto mt-[12vh] w-[min(640px,calc(100vw-32px))]"
      >
        <div className="flex items-center gap-2 border-b border-border px-3">
          <IconSearch />
          <input
            ref={input}
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="MAC, IP, cliente, modelo, router..."
            aria-label="Buscar"
            role="combobox"
            aria-expanded={shown.length > 0}
            aria-controls={listId}
            aria-activedescendant={shown.length ? optionId(active) : undefined}
            aria-autocomplete="list"
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="search"
            maxLength={100}
            className="h-12 flex-1 bg-transparent text-[15px] outline-none placeholder:text-faint"
          />
          {pending ? (
            <span className="status" data-state="running">
              <span className="dot" />
            </span>
          ) : null}
          <kbd>Esc</kbd>
        </div>
        <ul
          id={listId}
          role="listbox"
          aria-label="Resultados"
          className="max-h-[52vh] overflow-auto py-1"
        >
          {shown.map((hit, i) => (
            <li
              key={`${hit.kind}-${hit.mac}-${hit.title}-${i}`}
              id={optionId(i)}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onClick={() => go(hit)}
              className="flex cursor-pointer items-center gap-3 px-3 py-2 aria-selected:bg-raised aria-selected:shadow-[inset_2px_0_0_var(--accent)]"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate">{hit.title}</span>
                <span className="block truncate text-[12px] text-muted">
                  {hit.detail}
                </span>
              </span>
              {hit.kind === "device" ? <SignalMeter dbm={hit.signal} /> : null}
            </li>
          ))}
        </ul>
        <p
          className="border-t border-border px-3 py-2 text-[12px] text-muted"
          aria-live="polite"
        >
          {q.trim().length < 2
            ? "Escribi al menos 2 caracteres. Varias palabras: todas tienen que aparecer."
            : pending
              ? "Buscando..."
              : shown.length
                ? `${shown.length} resultados · Enter abre el detalle`
                : "Sin resultados · Enter busca en la tabla de equipos"}
        </p>
      </dialog>
    </>
  );
}
