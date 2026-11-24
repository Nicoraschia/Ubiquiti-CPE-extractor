import assert from "node:assert/strict";
import { test } from "node:test";

import { safeNext } from "./safe-next.ts";
import { signalBars, signalLabel, signalLevel } from "./signal.ts";
import {
  compareValues,
  ipKey,
  type SortDir,
  type SortValue,
  timeKey,
} from "./sort.ts";

test("safeNext solo acepta rutas internas", () => {
  assert.equal(safeNext("/equipos/aa:bb"), "/equipos/aa:bb");
  assert.equal(safeNext("/routers?q=huawei%20192"), "/routers?q=huawei%20192");
  for (const evil of [
    "//evil.com",
    "/\\evil.com",
    "https://evil.com",
    "evil.com",
    "",
    null,
    undefined,
    42,
  ]) {
    assert.equal(safeNext(evil), "/equipos", String(evil));
  }
  assert.equal(safeNext("/login?next=/x"), "/equipos"); // sin bucles de login
  // El parser de URL del navegador borra TAB/CR/LF: "/\t/evil" termina siendo "//evil".
  for (const evil of [
    "/\t/evil.com",
    "/\n/evil.com",
    "/\r/evil.com",
    "/\t\\evil.com",
  ]) {
    assert.equal(safeNext(evil), "/equipos", JSON.stringify(evil));
  }
  assert.equal(safeNext("/equipos?q=a%09b"), "/equipos?q=a%09b"); // codificado en la query es valido
});

test("umbrales de senal airOS", () => {
  assert.equal(signalLevel(-47), "ok");
  assert.equal(signalLevel(-65), "ok");
  assert.equal(signalLevel(-66), "warn");
  assert.equal(signalLevel(-75), "warn");
  assert.equal(signalLevel(-76), "crit");
  assert.equal(signalLevel(null), "none");
});

test("las barras codifican el nivel sin depender del color", () => {
  assert.deepEqual([-50, -60, -70, -80, null].map(signalBars), [4, 3, 2, 1, 0]);
  assert.equal(signalLabel(-74), "Senal -74 dBm, atencion");
  assert.equal(signalLabel(undefined), "Senal sin datos");
});

const sorted = (values: SortValue[], dir: SortDir) =>
  [...values].sort((a, b) => compareValues(a, b, dir));

test("orden alfabetico en espanol, sin distinguir mayusculas y con numeros naturales", () => {
  assert.deepEqual(
    sorted(["AVILA", " abel", "Ñandu", "Nuñez", "Ángel"], "asc"),
    [" abel", "Ángel", "AVILA", "Nuñez", "Ñandu"],
  );
  assert.deepEqual(sorted(["AP_10", "AP_2"], "asc"), ["AP_2", "AP_10"]);
});

test("numeros de menor a mayor y al reves; los vacios siempre al final", () => {
  assert.deepEqual(sorted([-47, null, -81, -5], "asc"), [-81, -47, -5, null]);
  assert.deepEqual(sorted([-47, null, -81, -5], "desc"), [-5, -47, -81, null]);
  assert.deepEqual(sorted(["", "b", "a"], "desc"), ["b", "a", ""]);
});

test("las IP y subnets ordenan como numeros y las fechas como fechas", () => {
  const byIp = (a: string, b: string) => ipKey(a)! - ipKey(b)!;
  assert.deepEqual(["192.168.9.10", "10.20.1.5", "192.168.9.2"].sort(byIp), [
    "10.20.1.5",
    "192.168.9.2",
    "192.168.9.10",
  ]);
  assert.deepEqual(["10.0.0.0/24", "10.0.0.0/8"].sort(byIp), [
    "10.0.0.0/8",
    "10.0.0.0/24",
  ]);
  assert.equal(ipKey(null), null);
  assert.equal(ipKey("no-ip"), null);
  assert.ok(
    timeKey("2026-11-22T10:00:00.5+00:00")! <
      timeKey("2026-11-22T08:00:00-03:00")!,
  );
});
