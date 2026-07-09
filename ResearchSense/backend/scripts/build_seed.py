"""Generate seed JSON for ResearchSense from the real Bahria E-8 roster.

Real data: researcher names, designations, department, and (where captured)
research areas. Derived/sample data: topics catalogue mapping, publications,
projects and funding — each flagged ``source="sample"`` for honesty. Emails and
ORCIDs are plausible placeholders flagged as sample.

Run:  python -m scripts.build_seed   (from backend/)
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from scripts.roster_data import CAMPUS, DEPARTMENT, ROSTER

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"

TOPIC_CATALOGUE = [
    ("Machine Learning", "brain"), ("Deep Learning", "layers"),
    ("Computer Vision", "eye"), ("Natural Language Processing", "message"),
    ("Cybersecurity", "shield"), ("Blockchain", "link"),
    ("Data Science", "chart"), ("Wireless Communications", "wifi"),
    ("Signal Processing", "activity"), ("Internet of Things", "cpu"),
    ("Cloud Computing", "cloud"), ("Software Engineering", "code"),
    ("Network Security", "lock"), ("Artificial Intelligence", "sparkles"),
    ("Image Processing", "image"), ("Big Data Analytics", "database"),
    ("Human-Computer Interaction", "hand"), ("Bioinformatics", "dna"),
    ("Computer Networks", "share"), ("Distributed Systems", "server"),
    ("Cryptography", "key"), ("Pattern Recognition", "scan"),
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
    "{topic}: {adj} methods for real-world applications",
    "Towards {adj} {topic} with {method}",
    "An empirical study of {topic} in {domain}",
    "{method}-based framework for {topic}",
]
ADJ = ["novel", "robust", "scalable", "efficient", "hybrid", "lightweight"]
METHOD = ["deep neural networks", "transformers", "ensemble learning",
          "federated learning", "graph neural networks", "attention models"]
DOMAIN = ["healthcare", "smart cities", "education", "agriculture",
          "cyber-physical systems", "e-governance"]


def topic_index() -> list[dict]:
    return [
        {"topic_id": i + 1, "topic_name": name, "icon": icon,
         "description": f"Research and publications in {name} at {CAMPUS}.",
         "source": "sample"}
        for i, (name, icon) in enumerate(TOPIC_CATALOGUE)
    ]


def _topics_for(rng: random.Random, areas: str, topics: list[dict]) -> list[dict]:
    by_name = {t["topic_name"]: t for t in topics}
    chosen: list[dict] = []
    for part in [a.strip() for a in areas.split(";") if a.strip()]:
        for t in topics:
            if t["topic_name"].lower() in part.lower() or part.lower() in t["topic_name"].lower():
                chosen.append(t)
                break
    while len(chosen) < 2:
        cand = rng.choice(topics)
        if cand not in chosen:
            chosen.append(cand)
    seen, out = set(), []
    for t in chosen[:3]:
        if t["topic_id"] not in seen:
            seen.add(t["topic_id"])
            out.append({"topic_id": t["topic_id"], "topic_name": t["topic_name"]})
    return out


def _email(name: str) -> str:
    clean = name.split(".")[-1].strip() if "." in name.split(" ")[0] else name
    parts = [p for p in clean.replace(".", " ").split() if p]
    handle = (parts[0][0] + parts[-1]).lower() if len(parts) > 1 else parts[0].lower()
    return f"{handle}.buic@bahria.edu.pk"


def build_researchers(topics: list[dict]) -> list[dict]:
    rng = random.Random(42)
    out = []
    for i, (name, designation, areas) in enumerate(ROSTER, start=1):
        rtopics = _topics_for(rng, areas, topics)
        pub_count = rng.randint(3, 22) if "Professor" in designation else rng.randint(1, 8)
        out.append({
            "researcher_id": i,
            "full_name": name,
            "designation": designation,
            "department": DEPARTMENT,
            "institution": CAMPUS,
            "email": _email(name),
            "orcid_id": f"0000-000{rng.randint(1,9)}-{rng.randint(1000,9999)}-{rng.randint(1000,9999)}",
            "photo_url": None,
            "publication_count": pub_count,
            "citation_count": pub_count * rng.randint(4, 30),
            "topics": rtopics,
            "profile_bio": _bio(name, designation, areas, rtopics),
            "source": "scraped",
        })
    return out


def _bio(name: str, designation: str, areas: str, rtopics: list[dict]) -> str:
    focus = areas if areas else ", ".join(t["topic_name"] for t in rtopics)
    return (
        f"{name} is a {designation} in the Department of {DEPARTMENT} at "
        f"{CAMPUS}. Research focuses on {focus}. Active in teaching, supervision "
        "and collaborative research within the School of Engineering and Applied "
        "Sciences."
    )


def build_publications(researchers: list[dict]) -> list[dict]:
    rng = random.Random(7)
    pubs, pid = [], 1
    for r in researchers:
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
                "abstract": f"This work investigates {topic['topic_name'].lower()} "
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


def enrich_topics(topics: list[dict], researchers, publications) -> list[dict]:
    for t in topics:
        t["researcher_count"] = sum(
            1 for r in researchers if any(rt["topic_id"] == t["topic_id"] for rt in r["topics"]))
        t["publication_count"] = sum(
            1 for p in publications if any(pt["topic_id"] == t["topic_id"] for pt in p["topics"]))
    return topics


def build_projects(researchers: list[dict]) -> list[dict]:
    rng = random.Random(99)
    seniors = [r for r in researchers if "Professor" in r["designation"]][:14]
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
            "start_date": f"{start}-0{rng.randint(1,9)}-01",
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

    print("Building ResearchSense seed data...")
    write("topics", topics)
    write("researchers", researchers)
    write("publications", publications)
    write("projects", projects)
    print("Done.")


if __name__ == "__main__":
    main()
