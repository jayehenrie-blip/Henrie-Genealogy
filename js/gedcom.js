/* Minimal GEDCOM 5.5.1 reader: turns the file into plain people and families objects. */
(function (global) {
  "use strict";

  function parseTree(text) {
    const root = { tag: "ROOT", children: [] };
    const stack = [root];
    const lines = text.split(/\r?\n/);
    for (const line of lines) {
      if (!line.trim()) continue;
      const m = line.match(/^\s*(\d+)\s+(@[^@]+@\s+)?(\w+)(?:\s(.*))?$/);
      if (!m) continue;
      const level = +m[1];
      const node = { id: m[2] ? m[2].trim().replace(/@/g, "") : null, tag: m[3], value: m[4] || "", children: [] };
      if (node.tag === "CONT") { stack[level].value += "\n" + node.value; continue; }
      if (node.tag === "CONC") { stack[level].value += node.value; continue; }
      while (stack.length > level + 1) stack.pop();
      stack[level].children.push(node);
      stack[level + 1] = node;
      stack.length = level + 2;
    }
    return root;
  }

  const first = (n, tag) => n.children.find(c => c.tag === tag);
  const all = (n, tag) => n.children.filter(c => c.tag === tag);
  const ref = v => (v || "").replace(/@/g, "");

  function readEvent(n) {
    if (!n) return null;
    const ev = { date: (first(n, "DATE") || {}).value || "", place: "", lat: null, lon: null };
    const pl = first(n, "PLAC");
    if (pl) {
      ev.place = pl.value;
      const map = first(pl, "MAP");
      if (map) {
        const la = (first(map, "LATI") || {}).value, lo = (first(map, "LONG") || {}).value;
        if (la && lo) {
          ev.lat = (la[0] === "S" ? -1 : 1) * parseFloat(la.slice(1));
          ev.lon = (lo[0] === "W" ? -1 : 1) * parseFloat(lo.slice(1));
        }
      }
    }
    const note = first(n, "NOTE");
    if (note) ev.note = note.value;
    return ev;
  }

  function parse(text) {
    const root = parseTree(text);
    const people = {}, families = {}, sources = {};
    for (const rec of root.children) {
      if (rec.tag === "INDI") {
        const nameNode = first(rec, "NAME");
        const raw = nameNode ? nameNode.value : "Unknown";
        const surname = (raw.match(/\/([^/]*)\//) || [, ""])[1].trim();
        const name = raw.replace(/\//g, "").replace(/\s+/g, " ").trim();
        const notes = all(rec, "NOTE").map(n => n.value);
        const sour = first(rec, "SOUR");
        people[rec.id] = {
          id: rec.id, name, surname,
          sex: (first(rec, "SEX") || {}).value || "",
          title: (first(rec, "TITL") || {}).value || "",
          living: !!first(rec, "_LIVING"),
          birth: readEvent(first(rec, "BIRT")),
          death: readEvent(first(rec, "DEAT")),
          burial: readEvent(first(rec, "BURI")),
          notes,
          pages: sour ? ((first(sour, "PAGE") || {}).value || "") : "",
          famc: ref((first(rec, "FAMC") || {}).value),
          fams: all(rec, "FAMS").map(f => ref(f.value)),
        };
      } else if (rec.tag === "FAM") {
        families[rec.id] = {
          id: rec.id,
          husb: ref((first(rec, "HUSB") || {}).value),
          wife: ref((first(rec, "WIFE") || {}).value),
          children: all(rec, "CHIL").map(c => ref(c.value)),
          marr: readEvent(first(rec, "MARR")),
        };
      } else if (rec.tag === "SOUR") {
        sources[rec.id] = { title: (first(rec, "TITL") || {}).value || "" };
      }
    }
    return { people, families, sources };
  }

  global.Gedcom = { parse };
})(window);
