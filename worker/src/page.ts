/**
 * The public streak page, server-rendered from D1.
 *
 * Served by the Worker itself, so there is no second deploy and no build step.
 * Kept deliberately small: rendering happens inside the free plan's 10 ms CPU
 * budget, so this is string concatenation over a capped row count.
 */

import type { Entry, WeekStats } from "./journal";

const STYLES = `
:root{--bg:#0d1410;--panel:#151f19;--line:#24352b;--text:#e7efe9;--muted:#8ba394;
--accent:#7fd18f;--accent-dim:#2f5a3c;--radius:14px}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 50% -10%,#16241b 0%,var(--bg) 60%);
color:var(--text);font:16px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;min-height:100vh}
main{max-width:760px;margin:0 auto;padding:4rem 1.25rem 5rem}
.eyebrow{margin:0 0 .5rem;text-transform:uppercase;letter-spacing:.18em;font-size:.72rem;color:var(--accent)}
h1{font-size:clamp(1.6rem,4vw,2.4rem);line-height:1.2;margin:0 0 2.5rem;font-weight:600}
h2{font-size:.8rem;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);margin:0 0 1rem}
.streak-card{display:flex;align-items:center;gap:2rem;flex-wrap:wrap;background:var(--panel);
border:1px solid var(--line);border-radius:var(--radius);padding:2rem;margin-bottom:1.5rem}
.streak-number{display:flex;align-items:baseline;gap:.35rem;color:var(--accent);font-variant-numeric:tabular-nums}
.streak-number b{font-size:clamp(3.5rem,12vw,5.5rem);font-weight:700;line-height:1}
.streak-unit{font-size:1rem;color:var(--muted)}
.streak-meta p{margin:.15rem 0;color:var(--muted);font-size:.9rem}
.panels{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:2.5rem}
@media(max-width:560px){.panels{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:1.25rem}
.chips{list-style:none;display:flex;flex-wrap:wrap;gap:.5rem;margin:0;padding:0}
.chips li{background:var(--accent-dim);border-radius:999px;padding:.3rem .7rem;font-size:.82rem}
.chips li.empty{background:none;color:var(--muted);padding:0}
.chips .count{color:var(--accent);margin-left:.35rem}
.entries{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.75rem}
.entries li{border-left:2px solid var(--accent-dim);padding:.25rem 0 .25rem 1rem}
.entries .date{display:block;font-size:.78rem;color:var(--muted);font-variant-numeric:tabular-nums}
.entries .summary{margin:.15rem 0 0}
.entries .meta{margin:.2rem 0 0;font-size:.82rem;color:var(--muted)}
.entries li.empty{border:0;padding:0;color:var(--muted)}
footer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid var(--line);color:var(--muted);font-size:.9rem}
`;

const escapeHtml = (s: string): string =>
  s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
  );

function chips(items: { name: string; count: number }[]): string {
  if (items.length === 0) return `<li class="empty">Nothing logged yet.</li>`;
  return items
    .map(
      (i) =>
        `<li>${escapeHtml(i.name)}${i.count > 1 ? `<span class="count">×${i.count}</span>` : ""}</li>`,
    )
    .join("");
}

function entryItems(entries: Entry[]): string {
  if (entries.length === 0) return `<li class="empty">No walks published yet.</li>`;
  return entries
    .map((e) => {
      const bits = [
        e.location,
        e.species.length ? e.species.join(", ") : null,
        e.mood,
      ].filter(Boolean) as string[];
      return (
        `<li><span class="date">${escapeHtml(e.localDate)}</span>` +
        `<p class="summary">${escapeHtml(e.summary)}</p>` +
        (bits.length ? `<p class="meta">${escapeHtml(bits.join(" · "))}</p>` : "") +
        `</li>`
      );
    })
    .join("");
}

export interface PageData {
  streak: number;
  week: WeekStats;
  totals: { walks: number; daysOut: number };
  entries: Entry[];
  generatedAt: string;
}

export function renderPage(d: PageData): string {
  const out = d.entries.filter((e) => e.outdoors).slice(0, 20);
  const dayWord = d.streak === 1 ? "day" : "days";
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Green Hour — a streak for going outside</title>
<meta name="description" content="How often I actually got off the screen and outside, logged by an open-source agent one voice note at a time.">
<style>${STYLES}</style>
</head>
<body>
<main>
<header>
<p class="eyebrow">Green Hour</p>
<h1>Getting off the screen, one voice note at a time.</h1>
</header>

<section class="streak-card">
<div class="streak-number"><b>${d.streak}</b><span class="streak-unit">${dayWord}</span></div>
<div class="streak-meta">
<p>This week: out ${d.week.daysOut} day${d.week.daysOut === 1 ? "" : "s"}, ${d.week.walks} walk${d.week.walks === 1 ? "" : "s"}.</p>
<p>${d.totals.walks} walks logged across ${d.totals.daysOut} days, all time.</p>
</div>
</section>

<section class="panels">
<div class="panel"><h2>Most heard</h2><ul class="chips">${chips(d.week.species)}</ul></div>
<div class="panel"><h2>Noticed</h2><ul class="chips">${chips(d.week.notable)}</ul></div>
</section>

<section>
<h2>Recent walks</h2>
<ol class="entries">${entryItems(out)}</ol>
</section>

<footer>
<p>Nudged and journalled by a Cloudflare Worker running open-weight models (Whisper + Qwen). The screen is the shortest part.</p>
<p>Snapshot ${escapeHtml(d.generatedAt)}.</p>
</footer>
</main>
</body>
</html>`;
}
