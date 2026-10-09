// Pages search engines can read.
//
// The app draws every page in the browser, so a crawler that does not run
// JavaScript (and every link preview) sees an empty <div id="root">: nobody
// can find a researcher by searching for their name. After `vite build`, this
// writes a real HTML file for every directory researcher and every paper,
// with a proper title, description, the page's text and schema.org data,
// plus sitemap.xml and robots.txt. The static host serves a file when one
// exists, so the crawler gets the content and a person gets the app, which
// replaces the static text as soon as it starts.
//
// Reads the same JSON the API serves (../backend/app/data). If that is not
// available to the build, it says so and leaves the build as it was.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.resolve(here, "..", "dist");
const DATA = path.resolve(here, "..", "..", "backend", "app", "data");
const SITE = (process.env.SITE_URL || "https://research-sense.vercel.app").replace(/\/$/, "");
const EXTENDED = "openalex"; // publication-only author records: not directory pages
const PAPERS_PER_PROFILE = 15;

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const clip = (s, n) => (s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s);
const jsonLd = (obj) => JSON.stringify(obj).replace(/</g, "\\u003c");

function load(name) {
  const file = path.join(DATA, `${name}.json`);
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : null;
}

function page(template, { url, title, description, body, data }) {
  const head = [
    `<title>${esc(title)}</title>`,
    `<meta name="description" content="${esc(description)}" />`,
    `<link rel="canonical" href="${esc(SITE + url)}" />`,
    `<meta property="og:title" content="${esc(title)}" />`,
    `<meta property="og:description" content="${esc(description)}" />`,
    `<meta property="og:url" content="${esc(SITE + url)}" />`,
    `<meta property="og:type" content="profile" />`,
    `<script type="application/ld+json">${jsonLd(data)}</script>`,
  ].join("\n    ");
  return template
    .replace(/<title>[\s\S]*?<\/title>/, "")
    .replace(/<meta\s+name="description"[\s\S]*?\/>/, "")
    .replace("</head>", `    ${head}\n  </head>`)
    .replace('<div id="root"></div>', `<div id="root"><main class="static-page">${body}</main></div>`);
}

// /researchers/8 is written as researchers/8.html: static hosts serve that
// file at the address without a slash (Vercel with cleanUrls, and Vite's
// preview), where a folder with an index.html only answers at /researchers/8/.
function write(url, html) {
  const parts = url.split("/").filter(Boolean);
  const dir = path.join(DIST, ...parts.slice(0, -1));
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, `${parts[parts.length - 1]}.html`), html);
}

function main() {
  const templatePath = path.join(DIST, "index.html");
  if (!fs.existsSync(templatePath)) {
    console.warn("prerender: no dist/index.html; run vite build first");
    return;
  }
  const researchers = load("researchers");
  const publications = load("publications");
  if (!researchers || !publications) {
    console.warn(`prerender: data not found at ${DATA}; skipping (the app still works)`);
    return;
  }
  const template = fs.readFileSync(templatePath, "utf8");
  const urls = ["/", "/researchers", "/publications", "/topics", "/departments"];

  const people = researchers.filter((r) => r.source !== EXTENDED);
  const byId = new Map(researchers.map((r) => [r.researcher_id, r]));
  const papersOf = new Map();
  for (const p of publications) {
    for (const a of p.authors ?? []) {
      if (a.researcher_id == null) continue;
      if (!papersOf.has(a.researcher_id)) papersOf.set(a.researcher_id, []);
      papersOf.get(a.researcher_id).push(p);
    }
  }

  for (const r of people) {
    const url = `/researchers/${r.researcher_id}`;
    const papers = (papersOf.get(r.researcher_id) ?? []).sort(
      (a, b) => (b.publication_year ?? 0) - (a.publication_year ?? 0),
    );
    const role = [r.designation, r.department].filter(Boolean).join(", ");
    const areas = (r.research_areas ?? []).slice(0, 5);
    const description = clip(
      `${r.full_name}${role ? `, ${role}` : ""}. ` +
        (areas.length ? `Works on ${areas.join(", ")}. ` : "") +
        `${papers.length} publication${papers.length === 1 ? "" : "s"} on ResearchSense.`,
      300,
    );
    const body =
      `<h1>${esc(r.full_name)}</h1>` +
      (role ? `<p>${esc(role)}${r.campus ? ` · ${esc(r.campus)}` : ""}</p>` : "") +
      (areas.length ? `<p>Research areas: ${areas.map(esc).join(", ")}</p>` : "") +
      (r.profile_bio ? `<p>${esc(clip(r.profile_bio, 600))}</p>` : "") +
      (papers.length
        ? `<h2>Publications</h2><ul>${papers
            .slice(0, PAPERS_PER_PROFILE)
            .map((p) => `<li><a href="/publications/${p.publication_id}">${esc(p.title)}</a> (${p.publication_year ?? "n.d."})</li>`)
            .join("")}</ul>`
        : "");
    const data = {
      "@context": "https://schema.org",
      "@type": "Person",
      name: r.full_name,
      jobTitle: r.designation || undefined,
      knowsAbout: areas.length ? areas : undefined,
      sameAs: r.orcid_id ? [`https://orcid.org/${r.orcid_id}`] : undefined,
      url: SITE + url,
    };
    write(url, page(template, { url, title: `${r.full_name} · ResearchSense`, description, body, data }));
    urls.push(url);
  }

  for (const p of publications) {
    const url = `/publications/${p.publication_id}`;
    const authors = (p.authors ?? []).map((a) => a.full_name);
    const description = clip(
      `${p.title}. ${authors.slice(0, 4).join(", ")}${authors.length > 4 ? " et al." : ""}` +
        `${p.journal_name ? `, ${p.journal_name}` : ""}${p.publication_year ? `, ${p.publication_year}` : ""}.`,
      300,
    );
    const body =
      `<h1>${esc(p.title)}</h1>` +
      `<p>${(p.authors ?? [])
        .map((a) =>
          a.researcher_id != null && byId.get(a.researcher_id)?.source !== EXTENDED
            ? `<a href="/researchers/${a.researcher_id}">${esc(a.full_name)}</a>`
            : esc(a.full_name),
        )
        .join(", ")}</p>` +
      `<p>${[p.journal_name, p.publication_year].filter(Boolean).map(esc).join(" · ")}</p>` +
      (p.abstract ? `<p>${esc(clip(p.abstract, 1200))}</p>` : "") +
      (p.doi ? `<p><a href="https://doi.org/${esc(p.doi)}">https://doi.org/${esc(p.doi)}</a></p>` : "");
    const data = {
      "@context": "https://schema.org",
      "@type": "ScholarlyArticle",
      headline: clip(p.title, 110),
      name: p.title,
      author: authors.map((name) => ({ "@type": "Person", name })),
      datePublished: p.publication_year ? String(p.publication_year) : undefined,
      isPartOf: p.journal_name ? { "@type": "Periodical", name: p.journal_name } : undefined,
      sameAs: p.doi ? `https://doi.org/${p.doi}` : undefined,
      url: SITE + url,
    };
    write(url, page(template, { url, title: `${clip(p.title, 90)} · ResearchSense`, description, body, data }));
    urls.push(url);
  }

  // Every top-level route needs a file of its own. With cleanUrls on, a
  // request for /guide is answered from guide.html; when that does not exist
  // the host returns 404 before the SPA rewrite is ever consulted, which took
  // every page but the home page off the live site. The shell is enough — the
  // app routes itself once loaded.
  const APP_ROUTES = [
    "/analytics",
    "/ask",
    "/collaboration",
    "/departments",
    "/guide",
    "/library",
    "/projects",
    "/publications",
    "/researchers",
    "/search",
    "/topics",
    // Sign-in pages are shells too, but robots.txt keeps them out of search.
    "/alerts",
    "/portal",
    "/staff-access",
  ];
  for (const route of APP_ROUTES) {
    write(route, template);
  }

  const sitemap =
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    urls.map((u) => `  <url><loc>${esc(SITE + u)}</loc></url>`).join("\n") +
    `\n</urlset>\n`;
  fs.writeFileSync(path.join(DIST, "sitemap.xml"), sitemap);
  fs.writeFileSync(
    path.join(DIST, "robots.txt"),
    `User-agent: *\nDisallow: /portal\nDisallow: /staff-access\nDisallow: /alerts\nDisallow: /api/\nSitemap: ${SITE}/sitemap.xml\n`,
  );
  console.log(`prerender: ${people.length} researcher and ${publications.length} paper pages, sitemap of ${urls.length} URLs`);
}

main();
