(() => {
  // Marker: if DevTools still shows api() at line ~8 calling /api/*, an old
  // cached bundle is running — path-versioned URLs should prevent that.
  const $ = (id) => document.getElementById(id);
  const version =
    (typeof window.__XL_ADDON_VERSION__ === "string" && window.__XL_ADDON_VERSION__) ||
    (typeof window.__ADDON_VERSION__ === "string" && window.__ADDON_VERSION__) ||
    "unknown";
  const assetVersion =
    (typeof window.__XL_ASSET_VERSION__ === "string" && window.__XL_ASSET_VERSION__) ||
    (typeof window.__ASSET_VERSION__ === "string" && window.__ASSET_VERSION__) ||
    "";
  const ingressInjected =
    (typeof window.__XL_INGRESS_PATH__ === "string" && window.__XL_INGRESS_PATH__) ||
    (typeof window.__INGRESS_PATH__ === "string" && window.__INGRESS_PATH__) ||
    "";
  console.log(
    `xLights DDP Bridge UI v${version}`,
    assetVersion ? `(assets ${assetVersion})` : "",
    "ingress=",
    ingressInjected || "(none)"
  );

  let available = [];
  let mapped = [];

  /**
   * Resolve under Ingress. Prefer injected X-Ingress-Path / <base href>.
   * Never use origin-root "/api/..." — that hits Home Assistant Core.
   */
  function bridgeBase() {
    if (ingressInjected) {
      return ingressInjected.replace(/\/+$/, "");
    }
    if (typeof window.__INGRESS_PATH__ === "string" && window.__INGRESS_PATH__) {
      return window.__INGRESS_PATH__.replace(/\/+$/, "");
    }
    const baseEl = document.querySelector("base");
    if (baseEl && baseEl.href) {
      try {
        const u = new URL(baseEl.href);
        const m = u.pathname.match(/^(.*?\/api\/hassio_ingress\/[^/]+)/);
        if (m) return m[1];
      } catch {
        /* ignore */
      }
    }
    const path = window.location.pathname || "/";
    const m = path.match(/^(.*?\/api\/hassio_ingress\/[^/]+)/);
    if (m) return m[1];
    // Sidebar panel URL is /app/<slug> — iframe src still has hassio_ingress
    try {
      if (window.frameElement && window.frameElement.src) {
        const iframePath = new URL(window.frameElement.src, window.location.origin)
          .pathname;
        const im = iframePath.match(/^(.*?\/api\/hassio_ingress\/[^/]+)/);
        if (im) return im[1];
      }
    } catch {
      /* cross-origin — ignore */
    }
    return "";
  }

  function apiUrl(path) {
    let cleaned = String(path).replace(/^\/+/, "");
    // Old bundles called "/api/status"; map to bridge/* under ingress
    if (cleaned === "api/status" || cleaned.startsWith("api/")) {
      cleaned = cleaned.replace(/^api\//, "bridge/");
    }
    const base = bridgeBase();
    // Absolute under ingress when known; else relative (honors <base href>)
    return base ? `${base}/${cleaned}` : cleaned;
  }

  function showBase() {
    const el = $("apiBase");
    if (!el) return;
    const resolved = apiUrl("bridge/status");
    el.textContent = `API base: ${bridgeBase() || "(relative + <base>)"} → ${resolved}`;
    const bad =
      resolved === "/api/status" ||
      (resolved.startsWith("/api/") &&
        !resolved.includes("hassio_ingress") &&
        !resolved.includes("/bridge/"));
    if (bad) {
      el.textContent +=
        " — still pointing at HA Core; update add-on and hard-refresh";
    }
  }

  function api(path, opts = {}) {
    const url = apiUrl(path);
    const headers = {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(opts.headers || {}),
    };
    // Ingress sometimes drops POST bodies; mirror JSON in a header as backup.
    if (
      opts.body &&
      typeof opts.body === "string" &&
      (opts.method || "GET").toUpperCase() !== "GET"
    ) {
      try {
        headers["X-Bridge-Body"] = btoa(
          unescape(encodeURIComponent(opts.body))
        );
      } catch {
        /* header optional */
      }
    }
    return fetch(url, {
      ...opts,
      credentials: "same-origin",
      headers,
    }).then(async (r) => {
      const text = await r.text();
      let data = {};
      try {
        data = text ? JSON.parse(text) : {};
      } catch {
        throw new Error(
          `Bad response from ${url} (${r.status}). Update/rebuild the add-on, then hard-refresh.`
        );
      }
      if (!r.ok) {
        const err = data.error || data.message || r.statusText || `HTTP ${r.status}`;
        throw new Error(
          `${typeof err === "string" ? err : JSON.stringify(err)} [${url}]`
        );
      }
      return data;
    });
  }

  function renderAvailable() {
    const q = ($("filter").value || "").toLowerCase();
    const ul = $("available");
    ul.innerHTML = "";
    available
      .filter((l) => !mapped.includes(l.entity_id))
      .filter(
        (l) =>
          !q ||
          l.entity_id.toLowerCase().includes(q) ||
          (l.name || "").toLowerCase().includes(q)
      )
      .forEach((l) => {
        const li = document.createElement("li");
        li.innerHTML = `<div class="meta"><div>${escapeHtml(l.name)}</div><div class="eid">${escapeHtml(l.entity_id)}</div></div>`;
        const btn = document.createElement("button");
        btn.textContent = "Add";
        btn.onclick = () => {
          mapped.push(l.entity_id);
          renderMapped();
          renderAvailable();
        };
        li.appendChild(btn);
        ul.appendChild(li);
      });
  }

  function renderMapped() {
    const ul = $("mapped");
    ul.innerHTML = "";
    mapped.forEach((eid, i) => {
      const meta = available.find((a) => a.entity_id === eid);
      const li = document.createElement("li");
      li.innerHTML = `<div class="meta"><div>${i}: ${escapeHtml(meta?.name || eid)}</div><div class="eid">${escapeHtml(eid)}</div></div>`;
      const up = document.createElement("button");
      up.textContent = "↑";
      up.disabled = i === 0;
      up.onclick = () => {
        [mapped[i - 1], mapped[i]] = [mapped[i], mapped[i - 1]];
        renderMapped();
        renderAvailable();
      };
      const down = document.createElement("button");
      down.textContent = "↓";
      down.disabled = i === mapped.length - 1;
      down.onclick = () => {
        [mapped[i + 1], mapped[i]] = [mapped[i], mapped[i + 1]];
        renderMapped();
        renderAvailable();
      };
      const rm = document.createElement("button");
      rm.textContent = "Remove";
      rm.onclick = () => {
        mapped.splice(i, 1);
        renderMapped();
        renderAvailable();
      };
      li.appendChild(up);
      li.appendChild(down);
      li.appendChild(rm);
      ul.appendChild(li);
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtAge(age) {
    if (age == null) return "never";
    if (age < 2) return `${age.toFixed(1)}s ago`;
    if (age < 60) return `${Math.round(age)}s ago`;
    return `${Math.round(age / 60)}m ago`;
  }

  function renderStatus(s) {
    const cells = [
      ["HA API", s.ha_ok == null ? "—" : s.ha_ok ? "OK" : "Issues", s.ha_ok === false ? "bad" : s.ha_ok ? "ok" : ""],
      ["DDP listening", s.listening ? `${s.ddp_bind}:${s.ddp_port}` : "no", s.listening ? "ok" : "bad"],
      ["Last peer", s.last_peer || "—", ""],
      ["Last packet", fmtAge(s.last_packet_age_s), ""],
      ["Packets/s", String(s.packets_per_second ?? 0), ""],
      [
        "Payload",
        s.payload_matches == null
          ? "—"
          : s.payload_matches
            ? `${s.last_payload_len} B OK`
            : `${s.last_payload_len} B (want ${s.expected_payload_len})`,
        s.payload_matches === false ? "bad" : s.payload_matches ? "ok" : "",
      ],
      ["Hz", String(s.hz), ""],
      ["Pixels", String((s.lights || []).length), ""],
    ];
    $("status").innerHTML = cells
      .map(
        ([k, v, cls]) =>
          `<div class="stat"><div class="k">${k}</div><div class="v ${cls}">${escapeHtml(v)}</div></div>`
      )
      .join("");

    const sw = $("swatches");
    sw.innerHTML = "";
    (s.last_colors || []).forEach((c, i) => {
      const d = document.createElement("div");
      d.className = "swatch";
      d.title = `${i}: ${s.lights?.[i] || "?"}`;
      if (c) d.style.background = `rgb(${c[0]},${c[1]},${c[2]})`;
      else d.style.background = "#222";
      sw.appendChild(d);
    });

    const ev = $("events");
    ev.innerHTML = (s.events || [])
      .map((e) => {
        const t = new Date((e.t || 0) * 1000).toLocaleTimeString();
        return `<li><span class="kind">${escapeHtml(e.kind)}</span>${escapeHtml(t)} — ${escapeHtml(e.message)}</li>`;
      })
      .join("") || "<li>No events yet</li>";
  }

  async function refreshStatus() {
    try {
      const s = await api("bridge/status");
      renderStatus(s);
    } catch (e) {
      $("status").textContent = String(e.message || e);
    }
  }

  async function load() {
    showBase();
    const [cfg, avail] = await Promise.all([
      api("bridge/config"),
      api("bridge/lights/available"),
    ]);
    $("hz").value = cfg.hz;
    mapped = cfg.lights || [];
    available = avail.lights || [];
    renderMapped();
    renderAvailable();
    await refreshStatus();
  }

  $("filter").addEventListener("input", renderAvailable);

  $("save").onclick = async () => {
    const hz = parseFloat($("hz").value);
    if (!mapped.length) {
      $("saveMsg").textContent =
        "Add at least one light to Mapped (click Add on the left), then Save.";
      return;
    }
    if (!Number.isFinite(hz) || hz < 0.1 || hz > 60) {
      $("saveMsg").textContent = "Hz must be a number between 0.1 and 60.";
      return;
    }
    $("saveMsg").textContent = "Saving…";
    try {
      await api("bridge/config", {
        method: "POST",
        body: JSON.stringify({
          lights: mapped,
          hz,
        }),
      });
      $("saveMsg").textContent = `Saved ${mapped.length} light(s) @ ${hz} Hz.`;
      await refreshStatus();
    } catch (e) {
      $("saveMsg").textContent = e.message || String(e);
    }
  };

  $("testHa").onclick = async () => {
    $("testOut").textContent = "Testing…";
    try {
      const r = await api("bridge/test/ha", { method: "POST", body: "{}" });
      $("testOut").textContent = JSON.stringify(r, null, 2);
      await refreshStatus();
    } catch (e) {
      $("testOut").textContent = e.message || String(e);
    }
  };

  $("pulseWhite").onclick = async () => {
    $("testOut").textContent = "Pulsing…";
    try {
      const r = await api("bridge/test/pulse", {
        method: "POST",
        body: JSON.stringify({ rgb: [255, 255, 255] }),
      });
      $("testOut").textContent = JSON.stringify(r, null, 2);
      await refreshStatus();
    } catch (e) {
      $("testOut").textContent = e.message || String(e);
    }
  };

  $("pulseOff").onclick = async () => {
    try {
      const r = await api("bridge/test/pulse", {
        method: "POST",
        body: JSON.stringify({ rgb: [0, 0, 0] }),
      });
      $("testOut").textContent = JSON.stringify(r, null, 2);
      await refreshStatus();
    } catch (e) {
      $("testOut").textContent = e.message || String(e);
    }
  };

  load().catch((e) => {
    showBase();
    $("status").textContent = e.message || String(e);
  });
  setInterval(refreshStatus, 2000);
})();
