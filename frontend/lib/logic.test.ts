import assert from "node:assert/strict";
import { test } from "node:test";

import { safeNext } from "./safe-next.ts";
import { signalBars, signalLabel, signalLevel } from "./signal.ts";

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
