/* The Henrie Family — a small, dependency-free family history viewer.
   Data: data/henrie.ged (GEDCOM 5.5.1). Views: story, family, fan (ancestors), journey (map). */
(function () {
  "use strict";
  const $ = s => document.querySelector(s);
  const view = $("#view");
  let DB = null;           // { people, families }
  let trail = [];          // people visited this session (for "You came from")
  let map = null;

  // ------------------------------------------------------------------ text helpers
  const MONTHS = { JAN: "January", FEB: "February", MAR: "March", APR: "April", MAY: "May", JUN: "June", JUL: "July", AUG: "August", SEP: "September", OCT: "October", NOV: "November", DEC: "December" };
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function words(d) {
    return d.replace(/\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b/g, m => MONTHS[m]);
  }
  function fmtDate(d) {
    if (!d) return "";
    let m = d.match(/^INT .*?\((.*)\)$/);
    if (m) return expandBook(m[1]);
    m = d.match(/^\((.*)\)$/); if (m) return expandBook(m[1]);
    if (/^ABT /.test(d)) return "about " + words(d.slice(4));
    if (/^BEF /.test(d)) return "before " + words(d.slice(4));
    if (/^AFT /.test(d)) return "after " + words(d.slice(4));
    m = d.match(/^BET (.*) AND (.*)$/); if (m) return `between ${words(m[1])} and ${words(m[2])}`;
    return words(d);
  }
  function expandBook(s) {
    const map = { "Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April", "Aug": "August", "Sept": "September", "Sep": "September", "Oct": "October", "Nov": "November", "Dec": "December" };
    return s.replace(/\b(Jan|Feb|Mar|Apr|Aug|Sept|Sep|Oct|Nov|Dec)\.?/g, m => map[m.replace(".", "")] || m).replace(/\babt\.?/i, "about");
  }
  const yearOf = ev => { if (!ev || !ev.date) return null; const m = ev.date.match(/\b(1[5-9]\d\d|20\d\d)\b/); return m ? +m[1] : null; };
  function span(p) {
    if (p.living) return "Living";
    const b = yearOf(p.birth), d = yearOf(p.death);
    const ab = p.birth && /^(ABT|INT|BET|\()/.test(p.birth.date) ? "abt. " : "";
    if (b && d) return `${ab}${b}–${d}`;
    if (b) return `born ${ab}${b}`;
    if (d) return `died ${d}`;
    return "";
  }
  function initials(n) { return n.replace(/\(.*?\)/g, "").split(/\s+/).filter(w => /^[A-Z]/.test(w)).slice(0, 2).map(w => w[0]).join(""); }
  function placeShort(pl) { return pl ? pl.replace(/\s*\(.*?\)\s*/g, " ").trim() : ""; }
  // The book's abbreviations, spelled out for reading (the GEDCOM keeps the original text).
  function plainWords(t) {
    return t
      .replace(/\bm\.\s*\((\d)\)/g, (m, n) => ["", "married first", "married second", "married third", "married fourth"][+n] || "married")
      .replace(/\bm\.(?=\s)/g, "married")
      .replace(/\bb\.(?=\s)/g, "born")
      .replace(/(^|[\s,;(])d\.(?=\s)/g, "$1died")
      .replace(/\bbur\.(?=\s)/g, "buried")
      .replace(/\bdau\.?(?=\s+of)/g, "daughter")
      .replace(/\bs\.(?=\s+of)/g, "son")
      .replace(/\babt\.(?=\s)/g, "about")
      .replace(/\bprob\.(?=\s)/g, "probably")
      .replace(/\bTwsp\./g, "Township");
  }
  const P = id => DB.people[id];
  const F = id => DB.families[id];

  function parentsOf(p) { const f = p.famc && F(p.famc); return f ? [f.husb, f.wife].filter(Boolean) : []; }
  function marriages(p) {
    return p.fams.map(fid => { const f = F(fid); if (!f) return null; const sp = f.husb === p.id ? f.wife : f.husb; return { f, spouse: sp ? P(sp) : null }; }).filter(Boolean);
  }
  const href = (id, mode) => `#/p/${id}${mode && mode !== "story" ? "/" + mode : ""}`;
  function card(id, mode, cls = "") {
    const p = P(id); if (!p) return "";
    return `<a class="pcard ${cls}" href="${href(id, mode)}"><span class="nm">${esc(p.name)}</span><span class="yr">${esc(span(p)) || "&nbsp;"}</span></a>`;
  }
  function relWord(child) { return child.sex === "M" ? "Son" : child.sex === "F" ? "Daughter" : "Child"; }

  // ------------------------------------------------------------------ routing
  function route() {
    if (!DB) return;
    const h = location.hash.replace(/^#\/?/, "");
    const parts = h.split("/");
    if (map) { map.remove(); map = null; }
    if (!$("#searchPanel").hidden) closeSearch();
    if (parts[0] === "p" && P(parts[1])) {
      const id = parts[1], mode = parts[2] || "story";
      if (trail[trail.length - 1] !== id) { trail = trail.filter(x => x !== id); trail.push(id); if (trail.length > 8) trail.shift(); }
      showViewbar(id, mode);
      const p = P(id);
      document.title = `${p.name} · The Henrie Family`;
      ({ story: renderStory, family: renderFamily, fan: renderFan, journey: renderJourney }[mode] || renderStory)(p);
    } else if (parts[0] === "about") {
      showViewbar(null); renderAbout(); document.title = "About · The Henrie Family";
    } else {
      showViewbar(null); renderHome(); document.title = "The Henrie Family";
    }
    window.scrollTo(0, 0);
  }
  function showViewbar(id, mode) {
    const bar = $("#viewbar");
    if (!id) { bar.hidden = true; return; }
    bar.hidden = false;
    bar.querySelectorAll("a").forEach(a => {
      a.href = href(id, a.dataset.mode);
      if (a.dataset.mode === mode) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
  }
  function backRow(p) {
    const prev = trail.length > 1 ? P(trail[trail.length - 2]) : null;
    return `<div class="backrow">
      ${prev ? `<a class="btn" href="${href(prev.id)}">← Back to ${esc(prev.name.split(" ")[0])}</a>` : ""}
      <a class="btn" href="#/">Home</a></div>`;
  }

  // ------------------------------------------------------------------ finders
  function find(name, year) {
    const n = name.toLowerCase();
    return Object.values(DB.people).find(p => p.name.toLowerCase() === n && (!year || yearOf(p.birth) === year));
  }

  // ------------------------------------------------------------------ home
  function renderHome() {
    const chain = [["Michael Henry", 1683], ["William Henry-Henrie", 1716], ["Michael Henry-Henrie", 1742], ["Daniel Henrie", 1780], ["William Henrie", 1799]]
      .map(([n, y]) => find(n, y)).filter(Boolean);
    const william = find("William Henrie", 1799);
    const kids = william ? marriages(william).flatMap(m => m.f.children) : [];
    const count = Object.keys(DB.people).length;
    view.innerHTML = `
      <section class="hero">
        <div class="eyebrow">The Red Book</div>
        <h1>The Henrie Family</h1>
        <p>The ancestors and descendants of William Henrie (1799–1883), the Utah pioneer, as gathered by Manetta (Prince) Henrie in 1954. This site holds ${count.toLocaleString()} people from the book.</p>
        <div class="row">
          ${william ? `<a class="btn primary" href="${href(william.id)}">Start with William Henrie</a>` : ""}
          <button class="btn" id="homeSearch">Find a name</button>
        </div>
      </section>
      <section>
        <h2 style="font-size:1.5rem;margin-bottom:6px">From Scotland to Utah</h2>
        <p class="muted small" style="margin-top:0">Five generations, oldest first. Tap a name to read about them.</p>
        <ol class="lineage">${chain.map(p => `<li><span class="rail"></span>${card(p.id)}</li>`).join("")}</ol>
      </section>
      ${kids.length ? `<section class="section"><h2>William and Myra's children</h2>
        <p class="muted small" style="margin-top:0">Most of the book follows the families of Daniel, James, Joseph and Samuel.</p>
        <div class="cards">${kids.map(id => card(id)).join("")}</div></section>` : ""}
      <section class="section"><h2>Four ways to look at each person</h2>
        <div class="cards">
          <div class="pcard ghost"><span class="nm">Story</span><span class="yr">Their life, dates and story from the book</span></div>
          <div class="pcard ghost"><span class="nm">Family</span><span class="yr">Parents, husband or wife, and children</span></div>
          <div class="pcard ghost"><span class="nm">Ancestors</span><span class="yr">A fan of grandparents going back in time</span></div>
          <div class="pcard ghost"><span class="nm">Journey</span><span class="yr">The places of their life on a map</span></div>
        </div></section>`;
    $("#homeSearch").onclick = openSearch;
  }

  // ------------------------------------------------------------------ story
  function storyParts(p) {
    const story = [], refs = [], ords = [], parents = [];
    for (const n of p.notes) {
      if (/^References?:/.test(n)) refs.push(n.replace(/^References?:\s*/, ""));
      else if (/^LDS ordinances/.test(n)) ords.push(n.replace(/^LDS ordinances as recorded in the book:\s*/, ""));
      else if (/^Parents:/.test(n)) parents.push(n.replace(/^Parents:\s*/, ""));
      else story.push(...n.split("\n").filter(x => x.trim()));
    }
    return { story, refs, ords, parents };
  }
  function renderStory(p) {
    const first = p.name.split(" ")[0];
    const s = storyParts(p);
    const facts = [];
    if (!p.living) {
      if (p.birth && (p.birth.date || p.birth.place)) facts.push(["Born", [fmtDate(p.birth.date), placeShort(p.birth.place)].filter(Boolean).join(", ")]);
      if (p.death && (p.death.date || p.death.place || p.death.note)) facts.push(["Died", [fmtDate(p.death.date), placeShort(p.death.place), p.death.note === "Died young" ? "died young" : ""].filter(Boolean).join(", ")]);
      if (p.burial && p.burial.place) facts.push(["Buried", placeShort(p.burial.place)]);
      for (const m of marriages(p)) {
        if (!m.spouse) continue;
        const when = m.f.marr ? [fmtDate(m.f.marr.date), placeShort(m.f.marr.place)].filter(Boolean).join(", ") : "";
        facts.push(["Married", `<a href="${href(m.spouse.id)}">${esc(m.spouse.name)}</a>${when ? `<br><span class="muted">${esc(when)}</span>` : ""}`, true]);
      }
      if (s.parents.length) facts.push(["Parents", plainWords(s.parents.join("; "))]);
    }
    const par = parentsOf(p);
    const ms = marriages(p);
    view.innerHTML = `
      ${backRow(p)}
      <div class="p-head">
        <div class="monogram" aria-hidden="true">${esc(initials(p.name))}</div>
        <div>${p.title ? `<div class="eyebrow">${esc(p.title)}</div>` : ""}<h1>${esc(p.name)}</h1><div class="lifespan">${esc(span(p))}</div></div>
      </div>
      ${p.living ? `<p class="living-note" style="margin-top:18px">${esc(first)} may still be living, so dates, places and stories are not shown on this public site.</p>` : `
      ${facts.length ? `<dl class="facts">${facts.map(([k, v, html]) => `<div><dt>${k}</dt><dd>${html ? v : esc(v)}</dd></div>`).join("")}</dl>` : ""}
      <div class="story">
        ${s.story.length ? `<h2>${esc(first)}'s story</h2>${s.story.map(x => `<p>${esc(plainWords(x))}</p>`).join("")}` : `<p class="muted">The Red Book has no written story for ${esc(first)}. Family members are welcome to send one.</p>`}
        <p class="src">From the Red Book${p.pages ? `, page ${esc(p.pages)}` : ""}.${s.refs.length ? " The book cites: " + esc(s.refs.join(" ")) : ""}</p>
        ${s.ords.length ? `<details class="ord"><summary>Church ordinance dates in the book</summary><p>${esc(s.ords.join("; "))}</p></details>` : ""}
      </div>`}
      <div class="fam-block">
        ${par.length ? `<h2>Parents</h2><div class="cards">${par.map(id => card(id)).join("")}</div>` : ""}
        ${ms.map(m => `
          <h2>${m.spouse ? `${ms.length > 1 ? "Family with" : "Married to"} ${esc(m.spouse.name)}` : "Children"}</h2>
          ${m.spouse ? `<div class="cards" style="margin-bottom:10px">${card(m.spouse.id)}</div>` : ""}
          ${m.f.children.length ? `<h3>Children (${m.f.children.length})</h3><div class="cards">${m.f.children.map(id => card(id)).join("")}</div>` : ""}
        `).join("")}
      </div>
      <p class="row" style="margin-top:24px"><a class="btn" href="${href(p.id, "family")}">See ${esc(first)}'s family tree</a></p>`;
  }

  // ------------------------------------------------------------------ family at a glance
  function renderFamily(p) {
    const par = parentsOf(p);
    const ms = marriages(p);
    const crumbs = trail.slice(0, -1).slice(-3).map(id => `<a href="${href(id, "family")}">${esc(P(id).name)}</a>`).join(" › ");
    const born = p.birth && p.birth.place && !p.living ? ` · ${placeShort(p.birth.place).split(",")[0]}` : "";
    view.innerHTML = `
      ${backRow(p)}
      ${crumbs ? `<p class="crumbs">You came from: ${crumbs} › <b>${esc(p.name)}</b></p>` : ""}
      <div class="tree">
        <div class="tlabel">Parents</div>
        <div class="trow">${par.length ? par.map(id => card(id, "family")).join("") : `<div class="pcard ghost"><span class="nm">Parents not recorded</span><span class="yr">Not in the Red Book</span></div>`}</div>
        <div class="vline"></div>
        <div class="couple">
          <a class="pcard focus" href="${href(p.id)}"><span class="nm">${esc(p.name)}</span><span class="yr">${esc(span(p))}${esc(born)} · read story</span></a>
          ${ms.length === 1 && ms[0].spouse ? `<span class="amp">&amp;</span>${card(ms[0].spouse.id, "family")}` : ""}
        </div>
        ${ms.map((m, i) => `
          <div class="marriage">
            ${ms.length > 1 && m.spouse ? `<div class="vline" style="margin:0 auto"></div><div class="marriage-h"><span class="tlabel">${["First", "Second", "Third", "Fourth", "Fifth"][i] || "Next"} marriage</span></div><div class="couple">${card(m.spouse.id, "family")}</div>` : ""}
            ${m.f.children.length ? `<div class="vline" style="margin:8px auto 0"></div><div class="tlabel" style="text-align:center">Children · ${m.f.children.length}</div><div class="cards kids">${m.f.children.map(id => card(id, "family")).join("")}</div>` : ""}
          </div>`).join("")}
        ${!ms.some(m => m.f.children.length) ? `<div class="vline"></div><div class="pcard ghost" style="max-width:360px"><span class="nm">No children listed</span><span class="yr">None are recorded in the book</span></div>` : ""}
      </div>`;
  }

  // ------------------------------------------------------------------ fan chart (ancestors)
  let fanGens = 5, fanSel = null;
  function renderFan(p) {
    if (fanSel && !P(fanSel)) fanSel = null;
    const W = 840, r0 = 78, ring = (W / 2 - 10 - r0) / (fanGens - 1), cx = W / 2, cy = W / 2 - 4, H = cy + 8;
    const colors = ["var(--cloth)", "var(--gold)", "var(--slate)", "var(--green)"];
    // gens[g] = array of ids (or null) length 2^g
    const gens = [[p.id]];
    for (let g = 1; g < fanGens; g++) {
      gens[g] = [];
      for (const id of gens[g - 1]) {
        const f = id && P(id).famc && F(P(id).famc);
        gens[g].push(f ? f.husb || null : null, f ? f.wife || null : null);
      }
    }
    let svg = "";
    const pt = (r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
    for (let g = 1; g < fanGens; g++) {
      const n = gens[g].length, rin = r0 + (g - 1) * ring, rout = rin + ring;
      gens[g].forEach((id, i) => {
        const a0 = Math.PI + (i / n) * Math.PI, a1 = Math.PI + ((i + 1) / n) * Math.PI;
        const [x0, y0] = pt(rin, a0), [x1, y1] = pt(rout, a0), [x2, y2] = pt(rout, a1), [x3, y3] = pt(rin, a1);
        const q = g === 1 ? (i === 0 ? 0 : 2) : Math.floor(i * 4 / n);
        const fill = id ? colors[q] : "var(--unknown)";
        const op = id ? Math.max(.55, 1 - (g - 1) * .13) : 1;
        const label = id ? P(id).name : "Unknown";
        svg += `<path class="fan-seg${fanSel === id && id ? " sel" : ""}" ${id ? `data-id="${id}" tabindex="0" role="button" aria-label="${esc(label + ", " + span(P(id)))}"` : 'aria-hidden="true"'} d="M${x0},${y0}L${x1},${y1}A${rout},${rout} 0 0 1 ${x2},${y2}L${x3},${y3}A${rin},${rin} 0 0 0 ${x0},${y0}Z" fill="${fill}" fill-opacity="${op}"/>`;
        // text
        const am = (a0 + a1) / 2, rm = (rin + rout) / 2, [tx, ty] = pt(rm, am), deg = am * 180 / Math.PI;
        const arc = (a1 - a0) * rm;
        if (!id) return;
        const nm = P(id).name.replace(/\s*\(.*?\)/g, "");
        const yrs = span(P(id));
        if (arc > ring * 1.1) {        // wide segment: text follows the arc
          const fs = Math.min(17, Math.max(11, arc / 11));
          const w = nm.split(" "), sur = w.length > 1 ? w.pop() : "", giv = w.join(" ");
          const fit = (s, px) => s.length * px * .55 > arc - 10 ? s.slice(0, Math.max(3, Math.floor((arc - 10) / (px * .55)) - 1)) + "…" : s;
          const ls = [fit(giv, fs), fit(sur, fs), fit(yrs, fs * .8)].filter(Boolean);
          svg += `<text class="fan-t" text-anchor="middle" transform="translate(${tx},${ty}) rotate(${deg + 90})">${ls.map((l, k) => `<tspan x="0" y="${(k - (ls.length - 1) / 2) * fs * 1.15 + fs * .35}" font-size="${k === 2 ? fs * .8 : fs}">${esc(l)}</tspan>`).join("")}</text>`;
        } else {                      // narrow segment: text runs outward
          const fs = Math.min(13, Math.max(8, arc * .42));
          const max = Math.floor((ring - 10) / (fs * .55));
          const w = nm.split(" "); let line1 = w.length > 1 ? `${w[0]} ${w[w.length - 1]}` : w[0];
          if (line1.length > max) line1 = line1.slice(0, max - 1) + "…";
          const rot = deg < 270 ? deg + 180 : deg;
          const two = arc > fs * 2.4;
          svg += `<text class="fan-t" text-anchor="middle" font-size="${fs}" transform="translate(${tx},${ty}) rotate(${rot})"><tspan x="0" y="${two ? -fs * .25 : fs * .35}">${esc(line1)}</tspan>${two ? `<tspan x="0" y="${fs * .95}" font-size="${fs * .85}">${esc(yrs)}</tspan>` : ""}</text>`;
        }
      });
    }
    svg += `<path class="fan-seg" data-id="${p.id}" tabindex="0" role="button" d="M${cx - r0},${cy}A${r0},${r0} 0 0 1 ${cx + r0},${cy}Z" fill="var(--ink)"/>
      <text class="fan-t" text-anchor="middle" style="fill:var(--bg)" font-size="16" x="${cx}" y="${cy - 38}">${esc(p.name.split(" ")[0])}</text>
      <text class="fan-t" text-anchor="middle" style="fill:var(--bg)" font-size="13" x="${cx}" y="${cy - 18}">${esc(span(p))}</text>`;
    const known = gens.slice(1).flat().filter(Boolean).length;
    const sel = fanSel ? P(fanSel) : null;
    view.innerHTML = `
      ${backRow(p)}
      <h1 style="font-size:1.7rem">${esc(p.name)}'s ancestors</h1>
      <p class="muted small" style="margin:.3rem 0 .8rem">Each ring is one generation back: parents, grandparents, great-grandparents. Tap a name to see who they are. Grey means the book does not name that person.</p>
      <div class="gens"><span class="small muted">Show</span>
        ${[3, 4, 5].map(g => `<button class="tool" data-gens="${g}" aria-pressed="${g === fanGens}" style="${g === fanGens ? "border-color:var(--cloth);background:var(--cloth-soft)" : ""}">${g - 1} generations</button>`).join("")}
      </div>
      <div class="fanwrap"><svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Fan chart of ${esc(p.name)}'s ancestors">${svg}</svg></div>
      <div class="legend">
        <span><span class="sw" style="background:var(--cloth)"></span>Father's father's line</span>
        <span><span class="sw" style="background:var(--gold)"></span>Father's mother's line</span>
        <span><span class="sw" style="background:var(--slate)"></span>Mother's father's line</span>
        <span><span class="sw" style="background:var(--green)"></span>Mother's mother's line</span>
        <span><span class="sw" style="background:var(--unknown);border:1px solid var(--line)"></span>Not named in the book</span>
      </div>
      <div class="detail" id="fanDetail">${sel ? `
        <b style="font-size:1.1rem">${esc(sel.name)}</b> <span class="muted">${esc(span(sel))}</span>
        ${!sel.living && sel.birth && sel.birth.place ? `<div class="small muted">Born ${esc(fmtDate(sel.birth.date))}${sel.birth.place ? ", " + esc(placeShort(sel.birth.place)) : ""}</div>` : ""}
        <div class="row" style="margin-top:10px"><a class="btn" href="${href(sel.id)}">Read ${esc(sel.name.split(" ")[0])}'s story</a><a class="btn" href="${href(sel.id, "fan")}">Center the fan on ${esc(sel.name.split(" ")[0])}</a></div>`
        : known ? `<span class="muted">The book names ${known} of ${esc(p.name.split(" ")[0])}'s ancestors in these ${fanGens - 1} generations. Tap any colored segment.</span>`
        : `<span class="muted">The Red Book does not name ${esc(p.name.split(" ")[0])}'s parents. Try someone born a Henrie, such as <a href="${href((find("Daniel Henrie", 1825) || p).id, "fan")}">Daniel Henrie (1825)</a>.</span>`}
      </div>`;
    view.querySelectorAll("[data-gens]").forEach(b => b.onclick = () => { fanGens = +b.dataset.gens; renderFan(p); });
    const pick = e => { const t = e.target.closest("[data-id]"); if (!t) return; fanSel = t.dataset.id === p.id ? null : t.dataset.id; renderFan(p); if (fanSel) $("#fanDetail").scrollIntoView({ block: "nearest", behavior: "smooth" }); };
    view.querySelector("svg").addEventListener("click", pick);
    view.querySelector("svg").addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(e); } });
  }

  // ------------------------------------------------------------------ journey (timeline + map)
  function lifeEvents(p) {
    const ev = [];
    const add = (what, e, who) => { if (!e || (!e.date && !e.place)) return; ev.push({ what, date: e.date, year: yearOf(e), place: e.place, lat: e.lat, lon: e.lon, who }); };
    add("Born", p.birth);
    for (const m of marriages(p)) {
      if (m.spouse && m.f.marr) add(`Married ${m.spouse.name}`, m.f.marr, m.spouse.id);
      for (const c of m.f.children) { const ch = P(c); if (!ch.living) add(`${relWord(ch)} ${ch.name.split(" ")[0]} born`, ch.birth, c); }
    }
    add("Died", p.death); add("Buried", p.burial);
    return ev.filter(e => e.year || e.place).sort((a, b) => (a.year || 9999) - (b.year || 9999));
  }
  function renderJourney(p) {
    if (p.living) { view.innerHTML = `${backRow(p)}<h1 style="font-size:1.7rem">${esc(p.name)}'s journey</h1><p class="living-note">${esc(p.name.split(" ")[0])} may still be living, so places are not shown.</p>`; return; }
    const ev = lifeEvents(p);
    const onMap = ev.filter(e => e.lat != null);
    const first = p.name.split(" ")[0];
    view.innerHTML = `
      ${backRow(p)}
      <h1 style="font-size:1.7rem">${esc(p.name)}'s journey</h1>
      <p class="muted small" style="margin:.3rem 0 1rem">The places in ${esc(first)}'s life, in order. Tap a line to find it on the map.</p>
      ${ev.length ? `<div class="journey">
        <div class="mapcol"><div id="map" role="region" aria-label="Map of places in ${esc(first)}'s life"></div>
          <p class="small muted">${onMap.length} of ${ev.length} events are on the map. A pin marked “+” holds several events in the same town. Positions are town centers.</p></div>
        <ol class="steps">${ev.map((e, i) => `<li><button class="step${e.lat == null ? " nomap" : ""}" data-i="${i}" aria-pressed="false">
            <span class="y">${e.year || "?"}</span>
            <span><span class="what">${esc(e.what)}</span><br><span class="where">${esc(placeShort(e.place) || "Place not recorded")}${e.date && !/^\d{4}$/.test(e.date) ? ` · ${esc(fmtDate(e.date))}` : ""}</span></span>
          </button></li>`).join("")}</ol>
      </div>` : `<p class="living-note">The Red Book records no dated places for ${esc(first)}.</p>`}`;
    if (!ev.length) return;
    let markers = [];
    if (window.L && onMap.length) {
      map = L.map("map", { scrollWheelZoom: false, tap: true });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 17, attribution: "© OpenStreetMap contributors" }).addTo(map);
      const pts = [], byPlace = {};
      ev.forEach((e, i) => {
        if (e.lat == null) return;
        pts.push([e.lat, e.lon]);
        const k = e.lat + "," + e.lon;
        (byPlace[k] = byPlace[k] || []).push(i);
      });
      Object.values(byPlace).forEach(idx => {
        const e0 = ev[idx[0]];
        const label = idx.length > 1 ? `${idx[0] + 1}+` : `${idx[0] + 1}`;
        const icon = L.divIcon({ className: "", html: `<div class="pin" data-pins="${idx.join(" ")}">${label}</div>`, iconSize: [36, 36], iconAnchor: [18, 18] });
        const list = idx.map(i => `<li><b>${i + 1}.</b> ${esc(ev[i].what)}${ev[i].year ? ` (${ev[i].year})` : ""}</li>`).join("");
        const mk = L.marker([e0.lat, e0.lon], { icon, title: placeShort(e0.place) }).addTo(map)
          .bindPopup(`<b>${esc(placeShort(e0.place))}</b><ol style="padding-left:0;list-style:none;margin:6px 0 0">${list}</ol>`, { maxWidth: 260 });
        mk.on("click", () => highlight(idx[0], false));
        idx.forEach(i => markers[i] = mk);
      });
      L.polyline(pts, { color: getComputedStyle(document.documentElement).getPropertyValue("--cloth").trim() || "#8a1c2b", weight: 3, dashArray: "6 8", opacity: .8 }).addTo(map);
      if (pts.length === 1) map.setView(pts[0], 9); else map.fitBounds(pts, { padding: [36, 36], maxZoom: 10 });
    } else {
      $("#map").innerHTML = `<p class="muted" style="padding:16px">${window.L ? "None of these places could be placed on the map." : "The map could not load. Check the internet connection."}</p>`;
    }
    function highlight(i, fly) {
      view.querySelectorAll(".step").forEach(b => b.setAttribute("aria-pressed", String(+b.dataset.i === i)));
      document.querySelectorAll(".pin").forEach(el => el.classList.toggle("on", el.dataset.pins.split(" ").includes(String(i))));
      const mk = markers[i];
      if (mk && fly) { map.flyTo(mk.getLatLng(), Math.max(map.getZoom(), 8), { duration: .6 }); mk.openPopup(); if (window.innerWidth <= 820) $("#map").scrollIntoView({ behavior: "smooth", block: "center" }); }
    }
    view.querySelectorAll(".step").forEach(b => b.onclick = () => highlight(+b.dataset.i, true));
  }

  // ------------------------------------------------------------------ about
  function renderAbout() {
    view.innerHTML = `<div class="about">
      <div class="backrow"><a class="btn" href="#/">Home</a></div>
      <h1>About this site</h1>
      <p>This site is built from <i>Ancestry and Descendants of William Henrie, 1799–1883</i>, compiled by Manetta (Prince) Henrie and published in Provo, Utah, in 1954. Ryan Henrie retyped and updated it as an electronic book in 2002 and asked that it be shared freely.</p>
      <h2>How the information was gathered</h2>
      <p>The book's text was converted into a standard family file (GEDCOM) by a computer program, then checked in places by hand. The book itself says that family history "is interesting, but not always accurate," and the conversion may have added mistakes of its own. Each person's page gives the book's page number so you can check the original.</p>
      <h2>People who may be living</h2>
      <p>Anyone born in the last 100 years without a recorded death shows their name only. Their dates, places and stories are kept out of this public site.</p>
      <h2>Corrections and additions</h2>
      <p>The Red Book is kept as the main source. New research, photos and corrections are added as separate, labeled sources and never change the book's own words.</p>
      <p><a class="btn" href="data/henrie.ged" download>Download the family file (GEDCOM)</a></p>
    </div>`;
  }

  // ------------------------------------------------------------------ search
  let index = [];
  const fold = s => s.toLowerCase().normalize("NFKD").replace(/[^a-z ]/g, " ").replace(/\bhenr(y|ie|ey)\b/g, "henrie").replace(/\s+/g, " ").trim();
  function buildIndex() { index = Object.values(DB.people).map(p => ({ id: p.id, k: fold(p.name), y: yearOf(p.birth) || 9999 })); }
  function search(q) {
    const t = fold(q).split(" ").filter(Boolean);
    if (!t.length || q.trim().length < 2) return [];
    return index.filter(r => t.every(w => r.k.split(" ").some(part => part.startsWith(w))))
      .sort((a, b) => a.y - b.y).slice(0, 60);
  }
  function openSearch() {
    $("#searchPanel").hidden = false; document.body.style.overflow = "hidden";
    const q = $("#q"); q.value = ""; $("#results").innerHTML = ""; $("#searchHint").hidden = false; setTimeout(() => q.focus(), 30);
  }
  function closeSearch() { $("#searchPanel").hidden = true; document.body.style.overflow = ""; }
  $("#searchBtn").onclick = openSearch;
  $("#closeSearch").onclick = closeSearch;
  $("#searchPanel").addEventListener("keydown", e => { if (e.key === "Escape") closeSearch(); });
  $("#q").addEventListener("input", e => {
    const r = search(e.target.value);
    $("#searchHint").hidden = r.length > 0;
    if (!r.length && e.target.value.trim().length >= 2) { $("#searchHint").hidden = false; $("#searchHint").textContent = "No one by that name. Try just a first name or a last name."; }
    else $("#searchHint").textContent = "Type at least two letters. Henry and Henrie are treated as the same.";
    $("#results").innerHTML = r.map(x => {
      const p = P(x.id), par = parentsOf(p).map(id => P(id).name.split(" ")[0]);
      return `<li><a class="pcard" href="${href(p.id)}"><span class="nm">${esc(p.name)}</span><span class="yr">${esc(span(p))}${par.length ? ` · child of ${esc(par.join(" & "))}` : ""}</span></a></li>`;
    }).join("");
  });
  $("#results").addEventListener("click", e => { if (e.target.closest("a")) closeSearch(); });

  // ------------------------------------------------------------------ text size
  let fs = 20;
  try { fs = +localStorage.getItem("henrie-fs") || 20; } catch (_) { }
  function setFs(v) { fs = Math.max(16, Math.min(30, v)); document.documentElement.style.setProperty("--fs", fs + "px"); try { localStorage.setItem("henrie-fs", fs); } catch (_) { } }
  $("#smaller").onclick = () => setFs(fs - 2);
  $("#bigger").onclick = () => setFs(fs + 2);
  setFs(fs);

  // ------------------------------------------------------------------ boot
  window.addEventListener("hashchange", route);
  fetch("data/henrie.ged").then(r => { if (!r.ok) throw new Error(r.status); return r.text(); })
    .then(t => { DB = Gedcom.parse(t); buildIndex(); route(); })
    .catch(err => { view.innerHTML = `<p class="living-note">The family file could not be opened (${esc(err.message)}). If you opened this page straight from your computer, it needs to be served from a web address such as GitHub Pages.</p>`; });
})();
