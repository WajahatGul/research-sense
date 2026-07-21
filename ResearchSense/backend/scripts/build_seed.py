"""Generate seed JSON for ResearchSense from the scraped Bahria faculty.

Real data (from bahria.edu.pk, via scrape_bahria.py): researcher names, campus,
department, designation, emails, research areas/expertise, and qualifications
across the four teaching campuses (E-8, H-11, Karachi, Lahore).

Derived / sample data (flagged source="sample"): projects and funding, which the
university does not publish in a single feed. Publications are added separately
by fetch_publications.py from OpenAlex (real data).

Run:  python -m scripts.build_seed   (from backend/)
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
SCRAPED = Path(__file__).resolve().parent / "scraped_faculty.json"
INSTITUTION = "Bahria University"


def canonical_designation(value: str) -> str:
    """Collapse the many spelling variants of a designation into one canonical
    form, so a role appears once in filters and reads consistently on cards.

    Scraped data mixes 'Sr.', 'Snr.', 'Senior.', and 'Sr' for 'Senior', varies
    the casing of professor/lecturer, and has the typo 'Lecture'. This only
    normalises those spellings; genuinely distinct compound roles (for example
    'Senior Lecturer / NCEAC Coordinator') stay separate.
    """
    s = (value or "").strip()
    if not s:
        return "Lecturer"
    s = re.sub(r"\b(?:Snr|Sr|Senior)\.?\s*", "Senior ", s, flags=re.I)
    s = re.sub(r"\blecture\b", "Lecturer", s, flags=re.I)
    s = re.sub(r"\blecturer\b", "Lecturer", s, flags=re.I)
    s = re.sub(r"\bprofessor\b", "Professor", s, flags=re.I)
    s = re.sub(r"\bassistant\b", "Assistant", s, flags=re.I)
    s = re.sub(r"\bassociate\b", "Associate", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()

# (canonical topic name, icon, keywords found in the real expertise text)
TOPIC_CATALOGUE = [
    ("Artificial Intelligence", "sparkles", ["artificial intelligence", "generative ai", "expert system", " ai ", "ai(", "ai ("]),
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
    ("Software Engineering", "code", ["software", "requirement engineering", "agile", "devops"]),
    ("Cloud Computing", "cloud", ["cloud", "virtualization", "edge computing"]),
    ("Blockchain", "link", ["blockchain", "ledger"]),
    ("Information Retrieval", "search", ["information retrieval", "retrieval", "search engine", "recommender"]),
    ("Digital Preservation", "archive", ["preservation", "digital curation", "digital archiv"]),
    ("Information Systems", "database", ["information system", "informatics", "database", "dbms", "data warehouse"]),
    ("Applied Mathematics", "function", ["mathematic", "fluid", "nanofluid", "numerical", "differential equation", "heat transfer"]),
    ("Pattern Recognition", "scan", ["pattern recognition", "biometric"]),
    ("Human Computer Interaction", "hand", ["human computer", "hci", "usability", "computer based learning", "e-learning"]),
    ("Bioinformatics", "dna", ["bioinformatic", "biomedical", "healthcare", "medical"]),
    ("Robotics", "bot", ["robot", "autonomous vehicle", "control system"]),
    ("Distributed Systems", "server", ["distributed", "parallel", "high performance", "grid computing"]),
]

FUNDERS = [
    ("Higher Education Commission (HEC)", "Pakistan"),
    ("National Research Program for Universities (NRPU)", "Pakistan"),
    ("Ignite National Technology Fund", "Pakistan"),
    ("Pakistan Science Foundation", "Pakistan"),
    ("ICT R&D Fund", "Pakistan"),
]
DOMAIN = ["healthcare", "smart cities", "education", "agriculture",
          "cyber physical systems", "e governance"]


def load_scraped() -> list[dict]:
    if not SCRAPED.exists():
        raise SystemExit("scraped_faculty.json not found. Run scrape_bahria first.")
    return json.loads(SCRAPED.read_text(encoding="utf-8"))


def topic_index() -> list[dict]:
    return [
        {"topic_id": i + 1, "topic_name": name, "icon": icon,
         "description": f"Research and expertise in {name} at {INSTITUTION}.",
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
    text = degree
    if majors:
        text += f" in {majors}"
    if uni:
        text += f" from {uni}"
    if year:
        text += f" ({year})"
    return text


def _bio(name, designation, department, campus, expertise, education) -> str:
    text = (f"{name} is a {designation} in the Department of {department} at "
            f"{INSTITUTION}, {campus} campus.")
    if expertise:
        text += f" Areas of expertise include {expertise.rstrip('.')}. "
    else:
        text += " "
    if education:
        text += f"Holds a {education}. "
    text += "Active in teaching, supervision and research."
    return text


def build_researchers(topics: list[dict]) -> list[dict]:
    rng = random.Random(42)
    out = []
    for i, rec in enumerate(load_scraped(), start=1):
        expertise = (rec.get("areas") or "").strip()
        campus = rec.get("campus", "Islamabad (E-8)")
        department = rec.get("department", "Computer Science")
        designation = canonical_designation(rec.get("designation", "Lecturer"))
        education = _education(rec)
        out.append({
            "researcher_id": i,
            "full_name": rec["name"],
            "designation": designation,
            "department": department,
            "campus": campus,
            "institution": INSTITUTION,
            "email": rec.get("email"),
            "orcid_id": None,
            "photo_url": None,
            "expertise": expertise,
            "publication_count": 0,
            "citation_count": 0,
            "topics": _topics_for(expertise, topics),
            "profile_bio": _bio(rec["name"], designation, department, campus,
                                expertise, education),
            "education": education,
            "source": "scraped",
        })
    return out


def enrich_topics(topics, researchers, publications):
    for t in topics:
        t["researcher_count"] = sum(
            1 for r in researchers if any(rt["topic_id"] == t["topic_id"] for rt in r["topics"]))
        t["publication_count"] = sum(
            1 for p in publications if any(pt["topic_id"] == t["topic_id"] for pt in p["topics"]))
    return topics


def build_projects(researchers: list[dict]) -> list[dict]:
    """Sample funded projects, spread across campuses, led by senior faculty."""
    rng = random.Random(99)
    seniors = [r for r in researchers
               if "Professor" in r["designation"] and r["topics"]]
    rng.shuffle(seniors)
    projects = []
    for i, pi in enumerate(seniors[:20], start=1):
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
            "department": pi["department"],
            "campus": pi["campus"],
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
    from collections import Counter

    topics = topic_index()
    researchers = build_researchers(topics)
    projects = build_projects(researchers)
    topics = enrich_topics(topics, researchers, [])

    by_campus = Counter(r["campus"] for r in researchers)
    real = sum(1 for r in researchers if r["email"])
    print("Building ResearchSense seed data...")
    print(f"  {len(researchers)} researchers across {len(by_campus)} campuses: "
          f"{dict(by_campus)}")
    print(f"  {real} have a real email")
    write("topics", topics)
    write("researchers", researchers)
    write("projects", projects)
    # Publications are written by fetch_publications.py (real, from OpenAlex).
    if not (DATA_DIR / "publications.json").exists():
        write("publications", [])
    print("Done. Next: python -m scripts.fetch_publications")


if __name__ == "__main__":
    main()
