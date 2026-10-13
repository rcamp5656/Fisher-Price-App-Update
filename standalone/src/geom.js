// ===== geom.js — disc mesh via manifold-3d (WASM), raised lettering via opentype.js, STL / SCAD / label card =====
const GEOM = (() => {
  const C = FP;
  let M = null, fontsP = null;
  const FONT_URLS = {
    bold: ["https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans-Bold.ttf", "DejaVu Sans:style=Bold", 0],
    rounded: ["https://raw.githubusercontent.com/google/fonts/main/ofl/comfortaa/Comfortaa%5Bwght%5D.ttf", "Comfortaa:style=Bold", 0.12],
    script: ["https://raw.githubusercontent.com/google/fonts/main/ofl/pacifico/Pacifico-Regular.ttf", "Pacifico", 0.08],
  };
  async function ready(onStatus = () => {}) {
    if (!M) { onStatus("loading 3D engine…"); const mod = await import("https://cdn.jsdelivr.net/npm/manifold-3d@3.4.1/manifold.js"); M = await mod.default(); M.setup(); }
    if (!fontsP) fontsP = (async () => { onStatus("loading fonts…"); const out = {}; for (const [k, [url]] of Object.entries(FONT_URLS)) { try { out[k] = window.opentype.parse(await (await fetch(url)).arrayBuffer()); } catch (e) { console.warn("font", k, e); } } if (!out.bold) throw new Error("Could not load the label font (internet needed once)"); return out; })();
    return { M, fonts: await fontsP };
  }

  // ---- 2D text outlines -> polygons (array of rings, each [[x,y],…]) ----
  function textPolys(font, text, size = 10) {
    const path = font.getPath(text, 0, 0, size), rings = []; let cur = [];
    const flat = (p) => { if (cur.length > 2) rings.push(cur); cur = []; };
    let x0 = 0, y0 = 0;
    for (const c of path.commands) {
      if (c.type === "M") { flat(); cur.push([c.x, -c.y]); x0 = c.x; y0 = c.y; }
      else if (c.type === "L") { cur.push([c.x, -c.y]); x0 = c.x; y0 = c.y; }
      else if (c.type === "Q" || c.type === "C") { const n = 6; for (let i = 1; i <= n; i++) { const t = i / n, mt = 1 - t; let x, y; if (c.type === "Q") { x = mt * mt * x0 + 2 * mt * t * c.x1 + t * t * c.x; y = mt * mt * y0 + 2 * mt * t * c.y1 + t * t * c.y; } else { x = mt ** 3 * x0 + 3 * mt * mt * t * c.x1 + 3 * mt * t * t * c.x2 + t ** 3 * c.x; y = mt ** 3 * y0 + 3 * mt * mt * t * c.y1 + 3 * mt * t * t * c.y2 + t ** 3 * c.y; } cur.push([x, -y]); } x0 = c.x; y0 = c.y; }
      else if (c.type === "Z") flat();
    }
    flat();
    return rings.filter((r) => Math.abs(area(r)) > 1e-6);
  }
  const area = (r) => { let a = 0; for (let i = 0; i < r.length; i++) { const [x1, y1] = r[i], [x2, y2] = r[(i + 1) % r.length]; a += x1 * y2 - x2 * y1; } return a / 2; };
  const bounds = (rings) => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const r of rings) for (const [x, y] of r) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); } return { x0, y0, x1, y1, w: x1 - x0, h: y1 - y0 }; };
  // flat, scaled, centred text (CrossSection) — fits height h and arc length; thin fonts get emboldened
  function textShape(font, text, r, h, arcDeg, fat = 0) {
    const rings = textPolys(font, text); if (!rings.length) return null;
    const b = bounds(rings), s = Math.min(h / Math.max(b.h, 1e-6), ((arcDeg * Math.PI) / 180) * r / Math.max(b.w, 1e-6));
    const cx = (b.x0 + b.x1) / 2, cy = (b.y0 + b.y1) / 2;
    const scaled = rings.map((ring) => ring.map(([x, y]) => [(x - cx) * s, (y - cy) * s]));
    let cs = new M.CrossSection(scaled, "EvenOdd");
    if (fat) cs = cs.offset(fat, "Round");
    return cs;
  }
  const segmentize = (ring, step) => { const out = []; for (let i = 0; i < ring.length; i++) { const [x1, y1] = ring[i], [x2, y2] = ring[(i + 1) % ring.length]; const n = Math.max(1, Math.ceil(Math.hypot(x2 - x1, y2 - y1) / step)); for (let k = 0; k < n; k++) out.push([x1 + ((x2 - x1) * k) / n, y1 + ((y2 - y1) * k) / n]); } return out; };
  // wrap x -> angle, y -> radius around the label arc (centre angle, tops outward, reads clockwise)
  function bend(cs, r, centre) { const polys = cs.toPolygons(); const warped = polys.map((ring) => segmentize(ring, 0.25).map(([x, y]) => { const th = centre - x / r; return [(r + y) * Math.cos(th), (r + y) * Math.sin(th)]; })); return new M.CrossSection(warped, "EvenOdd"); }
  function place(cs, angleDeg, radius) { return cs.translate([0, radius]).rotate(angleDeg - 90); }

  function textSolids(fonts, title, H, number, dedication, dedHeight, dedFont) {
    const shapes = [];
    if (title && title.trim()) { const t = textShape(fonts.bold, title.trim(), C.LABEL_R, C.LABEL_MAX_H, C.LABEL_MAX_ARC); if (t) shapes.push(bend(t, C.LABEL_R, C.ARC_CENTRE)); }
    if (dedication) { const f = fonts[dedFont] || fonts.bold, fat = FONT_URLS[fonts[dedFont] ? dedFont : "bold"][2]; const d = textShape(f, dedication, C.DED_R, dedHeight, C.DED_ARC, fat); if (d) shapes.push(bend(d, C.DED_R, (C.DED_CENTRE * Math.PI) / 180)); }
    if (number) { const num = textShape(fonts.bold, String(number), C.MARK_R, C.MARK_H, 120); if (num) shapes.push(place(num, 180, C.MARK_R)); shapes.push(place(M.CrossSection.square([3, 0.8], true), 0, C.MARK_R)); }
    return shapes.filter((s) => s.area() > 0.05).map((s) => M.Manifold.extrude(s, C.H_TEXT + C.OVERLAP).translate([0, 0, H - C.H_INSET - C.OVERLAP]));
  }
  function pinSolids(partition, H, comb, overrides, depth) {
    const pins = C.getPins(C.toPhysical(partition, comb, overrides)), half = C.pinBase(depth) / 2, z0 = H - C.H_GROOVE - C.OVERLAP;
    const cam = (d) => M.Manifold.extrude(new M.CrossSection([[[-d * C.PIN_SINK, -half], [-d * C.PIN_SINK, half], [0, half], [d * depth, 0], [0, -half]]]), C.H_GROOVE + C.OVERLAP);
    const cams = { 1: cam(1), [-1]: cam(-1) };
    return pins.map((p) => cams[p.dir].translate([p.wall, 0, z0]).rotate([0, 0, (p.angle * 180) / Math.PI]));
  }
  const flip = (m, H) => m.rotate([180, 0, 0]).translate([0, 0, H]);
  function grooves(H) { const gz = H - C.H_GROOVE / 2 + 0.2; return C.GROOVE_INNERS.map((inner) => M.Manifold.cylinder(C.H_GROOVE + 0.4, inner + 2, inner + 2, 200, true).subtract(M.Manifold.cylinder(C.H_GROOVE + 0.6, inner, inner, 200, true)).translate([0, 0, gz])); }

  function buildMesh(o) {
    const { partition, thickness: H, title = "", partitionB = null, titleB = "", marks = true, recordNo = 6, comb = C.DEFAULT_COMB, overrides = {}, overridesB = {}, pinRadius = C.R_PIN, dedHeight = C.DED_H, dedB = true, dedFont = "bold", fonts } = o;
    const cyl = (r, h, zc) => M.Manifold.cylinder(h, r, r, 160, true).translate([0, 0, zc]);
    let disc = cyl(C.R_STOCK, H, H / 2);
    const cuts = [cyl(C.R_CENTER, H + 1, H / 2)];
    for (const [dx, dy] of [[0, C.O_DRIVE], [0, -C.O_DRIVE], [C.O_DRIVE, 0], [-C.O_DRIVE, 0]]) cuts.push(cyl(C.R_DRIVE, H + 1, H / 2).translate([dx, dy, 0]));
    cuts.push(cyl(C.R_INSET, C.H_INSET + 0.4, H - C.H_INSET / 2 + 0.2), cyl(C.R_INSET, C.H_INSET + 0.4, C.H_INSET / 2 - 0.2));
    cuts.push(...grooves(H));
    if (partitionB) cuts.push(...grooves(H).map((g) => flip(g, H)));
    disc = disc.subtract(M.Manifold.union(cuts));
    let adds = pinSolids(partition, H, comb, overrides, pinRadius);
    let pinCount = adds.length;
    adds.push(...textSolids(fonts, title, H, marks ? recordNo : 0, C.DEDICATION, dedHeight, dedFont));
    if (partitionB) { const b = pinSolids(partitionB, H, comb, overridesB, pinRadius); pinCount += b.length; b.push(...textSolids(fonts, titleB, H, marks ? recordNo : 0, dedB ? C.DEDICATION : "", dedHeight, dedFont)); adds.push(...b.map((m) => flip(m, H))); }
    if (adds.length) disc = disc.add(M.Manifold.union(adds));
    const mesh = disc.getMesh();
    const props = mesh.numProp, verts = mesh.vertProperties, tris = mesh.triVerts;
    const pos = new Float32Array(tris.length * 3);
    for (let i = 0; i < tris.length; i++) { const v = tris[i] * props; pos[i * 3] = verts[v]; pos[i * 3 + 1] = verts[v + 1]; pos[i * 3 + 2] = verts[v + 2]; }
    const check = { ok: disc.status() === "NoError" && disc.genus() >= 0, volume: Math.round(disc.volume()), triangles: tris.length / 3, status: disc.status() };
    disc.delete();
    return { positions: pos, pinCount, check };
  }
  function toSTL(positions, name = "fisher-price-record") {
    const n = positions.length / 9, buf = new ArrayBuffer(84 + n * 50), dv = new DataView(buf);
    const head = `Fisher-Price Record Maker — ${name} — (c) 2026 Russ Campbell`.slice(0, 79); for (let i = 0; i < head.length; i++) dv.setUint8(i, head.charCodeAt(i) & 0x7f);
    dv.setUint32(80, n, true); let o = 84;
    for (let t = 0; t < n; t++) { const i = t * 9; const ax = positions[i + 3] - positions[i], ay = positions[i + 4] - positions[i + 1], az = positions[i + 5] - positions[i + 2], bx = positions[i + 6] - positions[i], by = positions[i + 7] - positions[i + 1], bz = positions[i + 8] - positions[i + 2];
      let nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx; const l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l;
      dv.setFloat32(o, nx, true); dv.setFloat32(o + 4, ny, true); dv.setFloat32(o + 8, nz, true); o += 12;
      for (let k = 0; k < 9; k++) { dv.setFloat32(o, positions[i + k], true); o += 4; } dv.setUint16(o, 0, true); o += 2; }
    return new Blob([buf], { type: "model/stl" });
  }

  // ---- per-character glyph placements for OpenSCAD ----
  function labelGlyphs(font, text, r, h, arcDeg, centreDeg) {
    text = (text || "").trim(); if (!text) return [];
    const full = bounds(textPolys(font, text)), s = Math.min(h / Math.max(full.h, 1e-6), ((arcDeg * Math.PI) / 180) * r / Math.max(full.w, 1e-6)), xc = (full.x0 + full.x1) / 2;
    const out = []; let prev = 0;
    for (let i = 0; i < text.length; i++) { const ch = text[i]; const ext = bounds(textPolys(font, text.slice(0, i + 1))); if (/\s/.test(ch)) { prev = ext.x1; continue; } const xm = i ? (prev + ext.x1) / 2 : (ext.x0 + ext.x1) / 2; prev = ext.x1; out.push([ch, Math.round((centreDeg - ((xm - xc) * s) / r * 180 / Math.PI) * 100) / 100, Math.round(10 * s * 1000) / 1000]); }
    return out;
  }
  const scadStr = (s) => (s || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  function toSCAD(o) {
    const { partition, thickness, title = "", partitionB = null, titleB = "", marks = true, recordNo = 6, comb = C.DEFAULT_COMB, overrides = {}, overridesB = {}, pinRadius = C.R_PIN, dedHeight = C.DED_H, dedB = true, dedFont = "bold", fonts } = o;
    const pinLines = (p, side, ov) => C.getPins(C.toPhysical(p, comb, ov)).map((q) => `\t\tpin(${Math.round(q.wall * 1000) / 1000},${Math.round((q.angle * 180) / Math.PI * 1000) / 1000},${q.dir},${side});`);
    const notes = pinLines(partition, "false", overrides); if (partitionB) { notes.push("\t\t// Side B"); notes.push(...pinLines(partitionB, "true", overridesB)); }
    const f = fonts[dedFont] || fonts.bold;
    const ded = (side) => labelGlyphs(f, C.DEDICATION, C.DED_R, dedHeight, C.DED_ARC, C.DED_CENTRE).map(([ch, a, s]) => `\t\tmark("${scadStr(ch)}",${a},dedR,${s},${side},dedFont);`);
    const labels = labelGlyphs(fonts.bold, title, C.LABEL_R, C.LABEL_MAX_H, C.LABEL_MAX_ARC, 180).map(([ch, a, s]) => `\t\tglyph("${scadStr(ch)}",${a},${s},false);`).concat(ded("false"));
    if (marks) labels.push(`\t\tmark("${recordNo}",180,markR,3.2,false);`, "\t\tdash(false);");
    if (partitionB) { labels.push(...labelGlyphs(fonts.bold, titleB, C.LABEL_R, C.LABEL_MAX_H, C.LABEL_MAX_ARC, 180).map(([ch, a, s]) => `\t\tglyph("${scadStr(ch)}",${a},${s},true);`)); if (dedB) labels.push(...ded("true")); if (marks) labels.push(`\t\tmark("${recordNo}",180,markR,3.2,true);`, "\t\tdash(true);"); }
    return `/* Generated by Fisher-Price Record Maker (HTML5 edition) on ${new Date().toLocaleString()}
 * Printable disc for the vintage Fisher-Price Music Box Record Player. Based on "Fred's Fisher Price record creator" template.
 * ${C.DEDICATION} — Copyright 2026 Russ Campbell
 * Side A: ${scadStr(title)}
 * Side B: ${partitionB ? scadStr(titleB) : ""}
 */

$fn = 100;
hStock = ${thickness};
rStock = 60.58;
oDrive = 21.8;
rDrive = 1.55;
hInset = 1;
rInset = 25.6;
hGroove = 1.2;
overlap = 0.2;
twoSided = ${partitionB ? "true" : "false"};
labelA = "${scadStr(title)}";
labelB = "${partitionB ? scadStr(titleB) : ""}";
labelR = 16.3;
dedR = ${C.DED_R};       // "${scadStr(C.DEDICATION)}" — small arc inside the title
dedFont = "${FONT_URLS[fonts[dedFont] ? dedFont : "bold"][1]}";
markR = 8.5;
hText = 0.6;
pinDepth = ${pinRadius};
pinBase = ${C.pinBase(pinRadius)};
pinSink = ${C.PIN_SINK};

module createDisc() {
\tunion() {
\t\tcreateBlank();
\t\t// Curved label text (dynamically generated)
${labels.join("\n")}
\t\t// Notes (dynamically generated)
${notes.join("\n")}
\t}
}

module createBlank() {
\tdifference() {
\t\tcylinder(h=hStock, r=rStock);
\t\ttranslate(v=[0,0,hStock-hInset+overlap]) { cylinder(h=hInset+overlap, r=rInset); }
\t\ttranslate(v=[0,0,-overlap]) { cylinder(h=hInset+overlap, r=rInset); }
\t\tcylinder(h=hStock, r=3.22);
\t\ttranslate(v=[0,oDrive,0]) { cylinder(h=hStock, r=rDrive); }
\t\ttranslate(v=[0,-oDrive,0]) { cylinder(h=hStock, r=rDrive); }
\t\ttranslate(v=[oDrive,0,0]) { cylinder(h=hStock, r=rDrive); }
\t\ttranslate(v=[-oDrive,0,0]) { cylinder(h=hStock, r=rDrive); }
\t\ttracks(false);
\t\tif (twoSided) tracks(true);
\t}
}
module onSide(onSecondSide) { if (onSecondSide) { translate(v=[0,0,hStock]) rotate(a=[180,0,0]) children(); } else { children(); } }
module tracks(onSecondSide) { onSide(onSecondSide) { track(28.15); track(30.89); track(33.71); track(36.425); track(39.225); track(42); track(44.825); track(47.555); track(50.315); track(53.11); track(55.9); } }
module track(inner) { translate(v=[0,0,hStock-hGroove]) { difference() { cylinder(h=hGroove+overlap, r=inner+2); cylinder(h=hGroove+overlap, r=inner); } } }
module glyph(ch, angle, size, onSecondSide) { mark(ch, angle, labelR, size, onSecondSide); }
module mark(ch, angle, r, size, onSecondSide, font="DejaVu Sans:style=Bold") {
\tonSide(onSecondSide) rotate(a=angle-90) translate(v=[0, r, hStock-hInset-overlap]) { linear_extrude(height=hText+overlap) { text(ch, size=size, halign="center", valign="center", font=font); } }
}
module dash(onSecondSide) { onSide(onSecondSide) translate(v=[markR, 0, hStock-hInset-overlap]) { linear_extrude(height=hText+overlap) { square(size=[3, 0.8], center=true); } } }
module pin(wall, angle, dir, onSecondSide) {
\thalf = pinBase / 2;
\tonSide(onSecondSide) rotate(a=angle) translate(v=[wall, 0, hStock-hGroove-overlap]) { linear_extrude(height=hGroove+overlap) { polygon(points=[[-dir*pinSink, -half], [-dir*pinSink, half], [0, half], [dir*pinDepth, 0], [0, -half]]); } }
}

createDisc();
`;
  }

  // ---- printable sleeve card (SVG, 100 x 60 mm) ----
  const ALBUM_COLOURS = ["#E63946", "#2A9D8F", "#FFB703", "#457B9D", "#8E44AD", "#F4845F", "#1D3557", "#6A994E", "#D77A61", "#5BC0BE"];
  function labelCard(rec, album = null) {
    const esc = (t) => String(t || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const fit = (t, size, w = 60) => ((t || "").length * size * 0.6 > w ? ` textLength="${w}" lengthAdjust="spacingAndGlyphs"` : "");
    const notes = (rec.notesUsed || []).map(C.noteName).join(" ");
    let badge = "", band = "";
    if (album) { const [i, n] = album, col = ALBUM_COLOURS[(i - 1) % ALBUM_COLOURS.length];
      badge = `<rect x="60" y="3" width="13" height="8" rx="1.5" fill="${col}"/><text x="66.5" y="8.8" font-size="4.5" font-weight="700" fill="#F4F1EA" text-anchor="middle">${i}/${n}</text><text x="66.5" y="15" font-size="2.6" fill="#457B9D" text-anchor="middle">disc ${i} of ${n}</text>`;
      const dots = Array.from({ length: Math.min(n, 10) }, (_, k) => `<circle cx="3.5" cy="${14 + k * 4.2}" r="1.1" fill="${ALBUM_COLOURS[k % 10]}" stroke="#F4F1EA" stroke-width="${k + 1 === i ? 0.5 : 0}"/>`).join("");
      band = `<rect x="0.5" y="0.5" width="6" height="59" rx="3" fill="${col}"/><rect x="3.5" y="0.5" width="3" height="59" fill="${col}"/>${dots}<text transform="translate(5,57) rotate(-90)" font-size="2.4" font-weight="700" fill="#F4F1EA">DISC ${i}</text>`; }
    const uid = Math.random().toString(36).slice(2, 8);
    return `<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60" font-family="DejaVu Sans, Arial, sans-serif" fill="#1D3557">
  <rect x="0.5" y="0.5" width="99" height="59" rx="3" fill="#F4F1EA" stroke="#1D3557" stroke-width="1"/>
  ${band}
  <circle cx="84" cy="14" r="9" fill="#B9A9E3" stroke="#1D3557" stroke-width="0.8"/>
  <circle cx="84" cy="14" r="1.5" fill="#F4F1EA" stroke="#1D3557" stroke-width="0.5"/>
  <defs><path id="ded-${uid}" d="M 73 14 A 11 11 0 1 1 95 14 A 11 11 0 1 1 73 14"/></defs>
  <text font-size="2.1" fill="#1D3557" letter-spacing="0.15"><textPath href="#ded-${uid}" startOffset="25%" text-anchor="middle">${esc(C.DEDICATION)}</textPath></text>
  <text x="84" y="29.5" font-size="2.8" text-anchor="middle" fill="#457B9D">RECORD</text>
  <text x="84" y="35" font-size="5" text-anchor="middle" font-weight="700">#${rec.recordNo || "-"}</text>
  ${badge}
  <text x="8" y="12" font-size="2.6" fill="#457B9D" textLength="54" lengthAdjust="spacingAndGlyphs">FISHER-PRICE MUSIC BOX RECORD PLAYER</text>
  <text x="8" y="22" font-size="4" fill="#457B9D">SIDE A</text>
  <text x="8" y="29" font-size="6" font-weight="700"${fit(rec.title, 6)}>${esc(rec.title)}</text>
  ${rec.twoSided ? `<text x="8" y="40" font-size="4" fill="#457B9D">SIDE B</text><text x="8" y="46" font-size="6" font-weight="700"${fit(rec.titleB, 6)}>${esc(rec.titleB)}</text>` : ""}
  <text x="8" y="51.5" font-size="2.6" fill="#457B9D" font-style="italic">${esc(C.DEDICATION)} · © 2026 Russ Campbell</text>
  <text x="8" y="55.5" font-size="2.8" fill="#457B9D">${rec.pinCount} pins · ${rec.thickness} mm · ${rec.duration}s window · ${esc(notes)}</text>
</svg>
`;
  }
  return { ready, buildMesh, toSTL, toSCAD, labelCard, ALBUM_COLOURS, textShape, bend };
})();
