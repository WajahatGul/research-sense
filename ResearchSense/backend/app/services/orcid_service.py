"""ORCID identity verification for profile claiming.

A claim is only allowed when the ORCID iD is structurally valid (ISO 7064
mod 11-2 checksum) AND the name registered on the public ORCID record matches
the researcher profile being claimed. This stops anyone claiming another
researcher's profile with their own (or an arbitrary) ORCID iD.

Uses the public ORCID registry API (pub.orcid.org, no key required). Full
possession proof would need ORCID OAuth sign-in; the registry name check is
the strongest verification available without registering an OAuth client.
"""
from __future__ import annotations

import re

import httpx

ORCID_PUBLIC_API = "https://pub.orcid.org/v3.0"
HEADERS = {"Accept": "application/json",
           "User-Agent": "ResearchSense/0.1 (mailto:dev@stocklenshq.com)"}

# Transliteration variants (same family as the retriever / authored modules)
# so "Rehman" on an ORCID record matches "Rahman" in the roster.
_NAME_VARIANTS = {
    "rehman": "rahman", "rahmaan": "rahman",
    "mohammad": "muhammad", "mohammed": "muhammad", "muhammed": "muhammad",
    "muhammd": "muhammad", "mohd": "muhammad",
    "sayed": "syed", "sayyed": "syed",
    "husain": "hussain", "hussein": "hussain",
    "othman": "usman", "uthman": "usman",
    "fatimah": "fatima",
}

# Connector particles common in names; never count them as identifying.
_PARTICLES = {"ur", "ul", "al", "bin", "binti", "ibn", "abu", "el", "de"}

_TITLES = r"^(dr|mr|ms|mrs|prof|professor|engr)\.?\s+"


class OrcidVerificationError(Exception):
    """User-facing ORCID verification failure."""


def checksum_valid(orcid_id: str) -> bool:
    """Validate the ORCID iD check digit (ISO 7064 mod 11-2)."""
    digits = orcid_id.replace("-", "").upper()
    if not re.fullmatch(r"\d{15}[\dX]", digits):
        return False
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    result = (12 - total % 11) % 11
    check = "X" if result == 10 else str(result)
    return digits[-1] == check


def _significant_tokens(name: str) -> set[str]:
    name = re.sub(_TITLES, "", name.strip(), flags=re.I)
    tokens = {
        _NAME_VARIANTS.get(t, t)
        for t in re.findall(r"[a-z]+", name.lower())
        if len(t) >= 2 and t not in _PARTICLES
    }
    return tokens


def fetch_record_names(orcid_id: str) -> list[str]:
    """All name variants on the public ORCID record (given+family,
    credit name, other names). Raises OrcidVerificationError on failure."""
    try:
        resp = httpx.get(f"{ORCID_PUBLIC_API}/{orcid_id}/person",
                         headers=HEADERS, timeout=20, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise OrcidVerificationError(
            "Could not reach the ORCID registry to verify your iD. "
            "Please try again.") from exc
    if resp.status_code == 404:
        raise OrcidVerificationError(
            "This ORCID iD does not exist in the ORCID registry.")
    if resp.status_code != 200:
        raise OrcidVerificationError(
            f"ORCID registry lookup failed (HTTP {resp.status_code}).")

    person = resp.json()
    names: list[str] = []
    name = person.get("name") or {}
    given = ((name.get("given-names") or {}).get("value") or "").strip()
    family = ((name.get("family-name") or {}).get("value") or "").strip()
    if given or family:
        names.append(f"{given} {family}".strip())
    credit = ((name.get("credit-name") or {}).get("value") or "").strip()
    if credit:
        names.append(credit)
    for other in ((person.get("other-names") or {}).get("other-name") or []):
        val = (other.get("content") or "").strip()
        if val:
            names.append(val)
    if not names:
        raise OrcidVerificationError(
            "The ORCID record has no public name to verify against. "
            "Make your name public on orcid.org or contact the admin.")
    return names


def _names_match(roster_name: str, record_name: str) -> bool:
    roster = _significant_tokens(roster_name)
    record = _significant_tokens(record_name)
    if not roster or not record:
        return False
    common = roster & record
    # Either one name is contained in the other (handles missing middle
    # names) or they share at least two identifying tokens.
    return roster <= record or record <= roster or len(common) >= 2


def verify_claim(orcid_id: str, researcher_name: str) -> None:
    """Raise OrcidVerificationError unless this ORCID iD plausibly belongs
    to the named researcher."""
    if not checksum_valid(orcid_id):
        raise OrcidVerificationError(
            "This is not a valid ORCID iD (checksum failed) - please "
            "double-check the digits.")
    record_names = fetch_record_names(orcid_id)
    if not any(_names_match(researcher_name, n) for n in record_names):
        shown = record_names[0]
        raise OrcidVerificationError(
            f"This ORCID iD is registered to \"{shown}\", which does not "
            f"match the profile of {researcher_name}. You can only claim "
            f"your own profile with your own ORCID iD.")
