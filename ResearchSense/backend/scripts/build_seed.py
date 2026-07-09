"""Generate seed JSON for ResearchSense from the real Bahria E-8 roster.

Real data (from bahria.edu.pk faculty pages, via scrape_bahria.py):
  researcher names, designations, department, emails, research areas/expertise,
  and highest qualification (degree, field, university).

Derived / sample data (flagged source="sample"):
  publications, projects and funding, and citation counts. These are not
  published on the university site.

Research areas are mapped from the real free text expertise to a canonical set
of topics so the portal can browse and filter and suggest collaborators.

Run:  python -m scripts.build_seed   (from backend/)
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from scripts.roster_data import CAMPUS, DEPARTMENT, ROSTER

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
SCRAPED = Path(__file__).resolve().parent / "scraped_faculty.json"

# (canonical topic name, icon, keywords found in the real expertise text)
TOPIC_CATALOGUE = [
    ("Artificial Intelligence", "sparkles", ["artificial intelligence", "generative ai", "expert system", " ai "]),
    ("Machine Learning", "brain", ["machine learning", "reinforcement learning"]),
    ("Deep Learning", "layers", ["deep learning", "neural network"]),
    ("Computer Vision", "eye", ["computer vision", "vision", "image recognition"]),
    ("Image Processing", "image", ["image processing", "medical imaging"]),
    ("Natural Language Processing", "message", ["natural language", "nlp", "text mining", "sentiment"]),
    ("Cybersecurity", "shield", ["security", "cyber", "cryptograph", "forensic", "malware"]),
    ("Computer Networks", "share", ["network", "sdn", "routing", "5g"]),
    ("Wireless Communications", "wifi", ["wireless", "communication", "signal", "digital twin", "antenna"]),
    ("Internet of Things", "cpu", ["internet of things", "iot", "sensor"]),
    ("Data Science", "chart", ["data science", "data mining", "big data", "data analytics", "data modeling", "statistical"]),
    ("Software Engineering", "code", ["software", "requirement engineering", "agile"]),
    ("Cloud Computing", "cloud", ["cloud", "virtualization"]),
    ("Blockchain", "link", ["blockchain", "ledger"]),
    ("Information Retrieval", "search", ["information retrieval", "retrieval", "search engine"]),
    ("Digital Preservation", "archive", ["preservation", "digital curation", "digital archiv"]),
    ("Information Systems", "database", ["information system", "informatics", "database", "dbms", "data warehouse"]),
    ("Applied Mathematics", "function", ["mathematic", "fluid", "nanofluid", "numerical", "differential equation", "heat transfer"]),
    ("Pattern Recognition", "scan", ["pattern recognition", "biometric"]),
    ("Human Computer Interaction", "hand", ["human computer", "hci", "usability", "computer based learning", "e-learning", "higher education"]),
    ("Bioinformatics", "dna", ["bioinformatic", "biomedical", "healthcare", "medical"]),
    ("Distributed Systems", "server", ["distributed", "parallel", "high performance", "grid computing"]),
]

JOURNALS = [
    "IEEE Access", "IEEE Transactions on Neural Networks", "Applied Sciences",
    "Sensors (MDPI)", "Journal of Network and Computer Applications",
    "Computers, Materials & Continua", "Electronics (MDPI)",
    "Future Generation Computer Systems", "Neural Computing and Applications",
    "IEEE Internet of Things Journal",
]
CONFERENCES = [
    "IEEE INMIC", "IEEE ICET", "FIT (Frontiers of Information Technology)",
    "IBCAST", "IEEE HONET",
]
FUNDERS = [
    ("Higher Education Commission (HEC)", "Pakistan"),
    ("National Research Program for Universities (NRPU)", "Pakistan"),
    ("Ignite National Technology Fund", "Pakistan"),
    ("Pakistan Science Foundation", "Pakistan"),
    ("ICT R&D Fund", "Pakistan"),
]
TITLE_TEMPLATES = [
    "A {adj} approach to {topic} using {method}",
    "{topic}: {adj} methods for real world applications",
    "Towards {adj} {topic} with {method}",
    "An empirical study of {topic} in {domain}",
    "{method} based framework for {topic}",
]
ADJ = ["novel", "robust", "scalable", "efficient", "hybrid", "lightweight"]
METHOD = ["deep neural networks", "transformers", "ensemble learning",
          "federated learning", "graph neural networks", "attention models"]
DOMAIN = ["healthcare", "smart cities", "education", "agriculture",
          "cyber physical systems", "e governance"]

# One site typo: the detail page spells "Faisal Imran" as "Faisal lmran".
ALIASES = {"faisallmran": "faisalimran"}


def _key(name: str) -> str:
    name = re.sub(r"^(dr|mr|ms|mrs|prof|engr)\.?\s*", "", name.strip().lower())
    key = re.sub(r"[^a-z]", "", name)
    return ALIASES.get(key, key)


def load_scraped() -> dict[str, dict]:
    if not SCRAPED.exists():
        return {}
    rows = json.loads(SCRAPED.read_text(encoding="utf-8"))
    return {_key(r["name"]): r for r in rows}


def topic_index() -> list[dict]:
    return [
        {"topic_id": i + 1, "topic_name": name, "icon": icon,
         "description": f"Research and expertise in {name} at {CAMPUS}.",
         "source": "sample"}
        for i, (name, icon, _kw) in enumerate(TOPIC_CATALOGUE)
    ]


def _topics_for(expertise: str, topics: list[dict]) -> list[dict]:
    text = f" {expertise.lower()} "
    chosen = []
    for (name, _icon, keywords), topic in zip(TOPIC_CATALOGUE, topics):
        if any(k in text for k in keywords):
            chosen.append({"topic_id": topic["topic_id"], "topic_name": name})
    return chosen[:4]


def _education(rec: dict) -> str:
    degree = (rec.get("degree") or "").strip()
    if not degree:
        return ""
    majors = (rec.get("degree_majors") or "").strip()
    uni = (rec.get("degree_university") or "").strip().rstrip(".")
    year = (rec.get("degree_year") or "").strip()
    parts = degree
    if majors:
        parts += f" in {majors}"
    if uni:
        parts += f" from {uni}"
    if year:
        parts += f" ({year})"
    return parts


def _bio(name: str, designation: str, expertise: str, education: str) -> str:
    text = (f"{name} is a {designation} in the Department of {DEPARTMENT} at "
            f"{CAMPUS}.")
    if expertise:
        text += f" Areas of expertise include {expertise.rstrip('.')}. "
    else:
        text += " "
    if education:
        text += f"Holds a {education}. "
    text += ("Active in teaching, supervision and research within the School of "
             "Engineering and Applied Sciences.")
    return text


def build_researchers(topics: list[dict]) -> list[dict]:
    scraped = load_scraped()
    rng = random.Random(42)
    out = []
    for i, (name, designation, manual_areas) in enumerate(ROSTER, start=1):
        rec = scraped.get(_key(name), {})
        expertise = (rec.get("areas") or manual_areas or "").strip()
        rtopics = _topics_for(expertise, topics)
        education = _education(rec)
        has_data = bool(expertise)
        pub_count = 0
        if has_data:
            pub_count = (rng.randint(4, 22) if "Professor" in designation
                         else rng.randint(1, 8))
        out.append({
            "researcher_id": i,
            "full_name": name,
            "designation": designation,
            "department": DEPARTMENT,
            "institution": CAMPUS,
            "email": rec.get("email"),
            "orcid_id": None,
            "photo_url": None,
            "expertise": expertise,
            "publication_count": pub_count,
            "citation_count": pub_count * rng.randint(4, 30),
            "topics": rtopics,
            "profile_bio": _bio(name, designation, expertise, education),
            "education": education,
            "source": "scraped",
        })
    return out


def build_publications(researchers: list[dict]) -> list[dict]:
    rng = random.Random(7)
    pubs, pid = [], 1
    for r in researchers:
        if not r["topics"]:
            continue
        for _ in range(min(r["publication_count"], 12)):
            topic = rng.choice(r["topics"])
            is_conf = rng.random() < 0.35
            title = rng.choice(TITLE_TEMPLATES).format(
                topic=topic["topic_name"].lower(), adj=rng.choice(ADJ),
                method=rng.choice(METHOD), domain=rng.choice(DOMAIN),
            ).capitalize()
            year = rng.randint(2017, 2025)
            pubs.append({
                "publication_id": pid,
                "title": title,
                "abstract": f"This work studies {topic['topic_name'].lower()} "
                            f"and reports results relevant to {rng.choice(DOMAIN)}.",
                "doi": f"10.1109/RS.{year}.{1000 + pid}",
                "publication_year": year,
                "journal_name": rng.choice(CONFERENCES if is_conf else JOURNALS),
                "publication_type": "conference" if is_conf else "journal",
                "citation_count": rng.randint(0, 60),
                "authors": [{"researcher_id": r["researcher_id"],
                             "full_name": r["full_name"], "order": 1}],
                "topics": [topic],
                "source": "sample",
            })
            pid += 1
    return pubs


def enrich_topics(topics, researchers, publications):
    for t in topics:
        t["researcher_count"] = sum(
            1 for r in researchers if any(rt["topic_id"] == t["topic_id"] for rt in r["topics"]))
        t["publication_count"] = sum(
            1 for p in publications if any(pt["topic_id"] == t["topic_id"] for pt in p["topics"]))
    return topics


def build_projects(researchers: list[dict]) -> list[dict]:
    rng = random.Random(99)
    seniors = [r for r in researchers
               if "Professor" in r["designation"] and r["topics"]][:14]
    projects = []
    for i, pi in enumerate(seniors, start=1):
        topic = rng.choice(pi["topics"])["topic_name"]
        start = rng.randint(2020, 2024)
        agency, country = rng.choice(FUNDERS)
        projects.append({
            "project_id": i,
            "project_title": f"{topic} for {rng.choice(DOMAIN).title()}",
            "description": f"A funded research project applying {topic.lower()} "
                           f"to {rng.choice(DOMAIN)} challenges in Pakistan.",
            "start_date": f"{start}-{rng.randint(1,12):02d}-01",
            "end_date": f"{start + rng.randint(1,3)}-12-31",
            "status": rng.choice(["ongoing", "ongoing", "completed"]),
            "principal_investigator_id": pi["researcher_id"],
            "principal_investigator_name": pi["full_name"],
            "department": DEPARTMENT,
            "funding": [{
                "funding_id": i, "agency_name": agency, "country": country,
                "amount": rng.choice([2.5, 5.0, 7.5, 10.0, 15.0]) * 1_000_000,
                "currency": "PKR",
            }],
            "topics": [topic],
            "source": "sample",
        })
    return projects


def write(name: str, data) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / f"{name}.json").open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    print(f"  wrote {name}.json ({len(data)} records)")


def main() -> None:
    topics = topic_index()
    researchers = build_researchers(topics)
    publications = build_publications(researchers)
    topics = enrich_topics(topics, researchers, publications)
    projects = build_projects(researchers)

    real = sum(1 for r in researchers if r["email"])
    print("Building ResearchSense seed data...")
    print(f"  {real}/{len(researchers)} researchers have real email + expertise")
    write("topics", topics)
    write("researchers", researchers)
    write("publications", publications)
    write("projects", projects)
    print("Done.")


if __name__ == "__main__":
    main()
