const $ = (id) => document.getElementById(id);

const state = {
  catalog: [],
  demo: [],
  filters: { q: "", issue: "", docType: "", category: "" },
  shown: 100,
};

const normalize = (s) => String(s || "").toLowerCase().replace(/\s+/g, "");

function scoreItem(it, q) {
  const code = normalize(it.code);
  const title = normalize(it.title);
  const cat = normalize(it.category);
  if (code.startsWith(q)) return 0;
  if (code.includes(q)) return 1;
  if (title.includes(q)) return 2;
  if (cat.includes(q)) return 3;
  return -1;
}

function issueBadge(issue) {
  const cls = issue === "现行" ? "ok" : issue === "待实施" ? "warn" : "bad";
  const el = document.createElement("span");
  el.className = "badge " + cls;
  el.textContent = issue || "未知";
  return el;
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function fillSelects() {
  const issues = new Set(), docs = new Set(), cats = new Set();
  for (const it of state.catalog) {
    if (it.issue) issues.add(it.issue);
    if (it.doc_type) docs.add(it.doc_type);
    if (it.category) cats.add(it.category);
  }
  for (const [sel, vals] of [
    ["f-issue", issues],
    ["f-doc", docs],
    ["f-cat", cats],
  ]) {
    const s = $(sel);
    for (const v of [...vals].sort((a, b) => a.localeCompare(b, "zh"))) {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = v;
      s.append(o);
    }
  }
}

function filteredCatalog() {
  const q = normalize(state.filters.q);
  return state.catalog
    .filter((it) => {
      if (state.filters.issue && it.issue !== state.filters.issue) return false;
      if (state.filters.docType && it.doc_type !== state.filters.docType) return false;
      if (state.filters.category && it.category !== state.filters.category) return false;
      if (q) {
        const s = scoreItem(it, q);
        if (s < 0) return false;
        it._score = s;
      } else {
        delete it._score;
      }
      return true;
    })
    .sort(
      (a, b) =>
        (a._score ?? 0) - (b._score ?? 0) ||
        (a.code || "").localeCompare(b.code || "")
    );
}

function renderCatalog() {
  const list = filteredCatalog();
  const shown = list.slice(0, state.shown);
  $("result-info").textContent = `共 ${list.length.toLocaleString()} 条，当前显示前 ${shown.length} 条`;
  $("load-more").hidden = list.length <= state.shown;

  const ul = $("results");
  ul.innerHTML = "";
  for (const it of shown) {
    const li = document.createElement("li");
    const top = el("div", "row-top");
    top.append(
      el("span", "code", it.code),
      el("span", "title", it.title),
      issueBadge(it.issue)
    );
    const meta = el("div", "meta");
    const parts = [];
    if (it.doc_type) parts.push(it.doc_type);
    if (it.category) parts.push(it.category);
    if (it.release_date) parts.push("发布 " + it.release_date);
    if (it.implementation_date) parts.push("实施 " + it.implementation_date);
    meta.textContent = parts.join(" · ");
    li.append(top, meta);
    if (it.source_url) {
      const a = el("a", "", "官方源");
      a.href = it.source_url;
      a.target = "_blank";
      a.rel = "noopener";
      const linkRow = el("div", "meta");
      linkRow.append(a);
      li.append(linkRow);
    }
    ul.append(li);
  }
  if (!shown.length) {
    const li = document.createElement("li");
    li.textContent = "没有匹配的记录。";
    ul.append(li);
  }
}

function renderDemo() {
  const q = normalize($("dq").value);
  const list = state.demo.filter((it) => {
    if (!q) return true;
    const hay = normalize(
      [it.standard_id, it.standard_title, it.article_no, it.summary, (it.tags || []).join(" ")].join(" ")
    );
    return hay.includes(q);
  });
  const info = $("demo-info");
  if (info) info.textContent = "共 " + list.length.toLocaleString() + " 条条目";
  const ul = $("demo-results");
  ul.innerHTML = "";
  for (const it of list) {
    const li = document.createElement("li");
    const top = el("div", "row-top");
    top.append(
      el("span", "code", it.standard_id),
      el("span", "title", `${it.standard_title || ""} · 第 ${it.article_no} 条`)
    );
    li.append(top, el("div", "summary", it.summary || ""));
    if (it.tags && it.tags.length) {
      const tags = el("div", "tags");
      for (const t of it.tags) tags.append(el("span", "tag", t));
      li.append(tags);
    }
    if (it.related && it.related.length) {
      const rel = el("div", "related");
      rel.textContent =
        "依据关联：" + it.related.map((r) => `${r.article}（${r.relation || ""}）`).join("；");
      li.append(rel);
    }
    if (it.source_url) {
      const a = el("a", "", "查看官方源");
      a.href = it.source_url;
      a.target = "_blank";
      a.rel = "noopener";
      const row = el("div", "related");
      row.append(a);
      li.append(row);
    }
    ul.append(li);
  }
  if (!list.length) {
    const li = document.createElement("li");
    li.textContent = "演示子集中没有匹配条目。";
    ul.append(li);
  }
}

function switchTab(name) {
  $("tab-catalog").classList.toggle("active", name === "catalog");
  $("tab-demo").classList.toggle("active", name === "demo");
  $("panel-catalog").hidden = name !== "catalog";
  $("panel-demo").hidden = name !== "demo";
}

document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".tab").forEach((b) =>
    b.addEventListener("click", () => switchTab(b.dataset.tab))
  );

  let debounce;
  $("q").addEventListener("input", (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      state.filters.q = e.target.value;
      state.shown = 100;
      renderCatalog();
    }, 150);
  });
  for (const [id, key] of [
    ["f-issue", "issue"],
    ["f-doc", "docType"],
    ["f-cat", "category"],
  ]) {
    $(id).addEventListener("change", (e) => {
      state.filters[key] = e.target.value;
      state.shown = 100;
      renderCatalog();
    });
  }
  $("btn-clear").addEventListener("click", () => {
    state.filters = { q: "", issue: "", docType: "", category: "" };
    $("q").value = "";
    $("f-issue").value = "";
    $("f-doc").value = "";
    $("f-cat").value = "";
    state.shown = 100;
    renderCatalog();
  });
  $("load-more").addEventListener("click", () => {
    state.shown += 100;
    renderCatalog();
  });
  let dqDebounce;
  $("dq").addEventListener("input", () => {
    clearTimeout(dqDebounce);
    dqDebounce = setTimeout(renderDemo, 120);
  });

  try {
    const [catalog, demo] = await Promise.all([
      fetch("data/public/catalog.json").then((r) => r.json()),
      fetch("data/public/demo.json").then((r) => r.json()),
    ]);
    state.catalog = catalog.items || [];
    state.demo = demo.items || [];
    fillSelects();
    renderCatalog();
    renderDemo();
  } catch (err) {
    $("result-info").textContent = "数据加载失败：" + err.message;
  }
});
