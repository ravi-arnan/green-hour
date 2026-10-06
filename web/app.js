// Renders the snapshot written by grass-report --publish.
// Plain DOM, no framework: the page is one fetch and one render.

const $ = (id) => document.getElementById(id);

function chips(target, items) {
  target.replaceChildren();
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "Nothing logged yet.";
    target.append(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.append(item.name);
    if (item.count > 1) {
      const span = document.createElement("span");
      span.className = "count";
      span.textContent = `×${item.count}`;
      li.append(span);
    }
    target.append(li);
  }
}

function renderEntries(container, entries) {
  container.replaceChildren();
  if (!entries || entries.length === 0) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "No walks published yet.";
    container.append(li);
    return;
  }
  for (const entry of entries) {
    const li = document.createElement("li");

    const date = document.createElement("span");
    date.className = "date";
    date.textContent = entry.date;
    li.append(date);

    const summary = document.createElement("p");
    summary.className = "summary";
    summary.textContent = entry.summary;
    li.append(summary);

    const bits = [];
    if (entry.location) bits.push(entry.location);
    if (entry.species && entry.species.length) bits.push(entry.species.join(", "));
    if (entry.mood) bits.push(entry.mood);
    if (bits.length) {
      const meta = document.createElement("p");
      meta.className = "meta";
      meta.textContent = bits.join(" · ");
      li.append(meta);
    }

    container.append(li);
  }
}

function render(data) {
  $("streak").textContent = data.streak ?? 0;
  $("streak-plural").textContent = (data.streak ?? 0) === 1 ? "" : "s";

  const week = data.week || {};
  $("week-line").textContent =
    week.walks != null
      ? `This week: out ${week.days_out} day${week.days_out === 1 ? "" : "s"}, ${week.walks} walk${week.walks === 1 ? "" : "s"}.`
      : "";

  const totals = data.totals || {};
  $("totals-line").textContent =
    totals.walks != null
      ? `${totals.walks} walks logged across ${totals.days_out} days, all time.`
      : "";

  chips($("species"), week.species);
  chips($("notable"), week.notable);
  renderEntries($("entries"), data.entries);

  if (data.generated_at) {
    $("generated").textContent = `Snapshot generated ${new Date(data.generated_at).toLocaleString()}.`;
  }
}

fetch("data/journal.json", { cache: "no-store" })
  .then((r) => {
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  })
  .then(render)
  .catch(() => {
    $("week-line").textContent = "The snapshot has not been published yet.";
    $("totals-line").textContent = "";
  });
