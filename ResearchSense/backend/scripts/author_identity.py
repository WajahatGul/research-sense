"""Does a name printed on a paper belong to a given profile?

The first matcher linked a printed name to a profile when any two words
agreed. In Pakistani names that is not evidence: "Syed", "Muhammad", "Ali",
"Khan" and "Haider" are shared by thousands of people, so "Syed Toqeer
Haider" was credited to Syed Haider Ali Shah (an HR professor), "Mohsin
Raza Khan" to Mohsin Hassan Khan, and forty papers by Muhammad Zunnurain
Hussain (Lahore, his own ORCID) to a Karachi professor named Muhammad
Hussain.

The rule asks what a careful reader would ask:

* Titles ("Dr", "Engr", "Rear Admiral", "Associate Professor") and
  punctuation are ignored; spacing does not matter ("Saif Ullah" is
  "Saifullah", "Fazl-e-Hadi" is "Fazle Hadi"); near spellings are the same
  word (Jawad/Jawwad, Feroz/Firoz) and an initial stands for its word.
* The names CONFLICT when each has a word the other lacks: "Mohsin Raza
  Khan" against "Mohsin Hasan Khan", "Syed Toqeer Haider" against "Syed
  Haider Ali Shah". A conflict is accepted only when two uncommon words
  agree ("Kashif Naseer Qureshi" for "Muhammad Kashif Naseer").
* A name that only leaves words out ("Safdar Rizvi") or only adds one
  ("Muhammad Talha Alam" for "Muhammad Talha") fits, provided an uncommon
  word agrees: "Muhammad Rahman" or "Muhammad Mazhar Hussain" says almost
  nothing about who wrote the paper.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache

_TITLES = {
    "dr",
    "engr",
    "cdr",
    "retd",
    "prof",
    "professor",
    "associate",
    "assistant",
    "lecturer",
    "mr",
    "mrs",
    "ms",
    "sir",
    "col",
    "lt",
    "maj",
    "capt",
    "captain",
    "rear",
    "admiral",
    "pn",
    "hafiz",
}

_SAME = {
    "rehman": "rahman",
    "rahmaan": "rahman",
    "mohammad": "muhammad",
    "mohammed": "muhammad",
    "muhammed": "muhammad",
    "mohamed": "muhammad",
    "mohd": "muhammad",
    "mohamad": "muhammad",
    "ahmed": "ahmad",
    "hussain": "husain",
    "hussein": "husain",
    "hassan": "hasan",
    "mehmood": "mahmood",
    "mahmud": "mahmood",
    "sayed": "syed",
    "sayyed": "syed",
}

# Name words so widely shared that agreeing on them proves nothing.
COMMON = {
    "muhammad",
    "syed",
    "ali",
    "khan",
    "ahmad",
    "husain",
    "hasan",
    "shah",
    "malik",
    "abdul",
    "ur",
    "ul",
    "rahman",
    "haider",
    "raza",
    "iqbal",
    "qureshi",
    "butt",
    "mahmood",
    "akhtar",
    "aslam",
    "rana",
    "chaudhry",
    "sheikh",
    "mirza",
    "khalid",
    "tariq",
    "imran",
    "asif",
    "bibi",
    "begum",
    "noor",
    "din",
    "ullah",
    "abbas",
    "javed",
    "rashid",
    "saeed",
    "zafar",
    "bilal",
    "usman",
    "umar",
    "hamid",
    "shahid",
    "nawaz",
    "anwar",
    "jamil",
}


def words(name: str) -> list[str]:
    raw = re.findall(r"[a-z]+", name.lower())
    return [_SAME.get(w, w) for w in raw if w not in _TITLES]


def _compact(ws: list[str]) -> str:
    return "".join(ws).replace("e", "")  # "fazl e hadi" ~ "fazle hadi"


@lru_cache(maxsize=200_000)
def _same_word(a: str, b: str) -> bool:
    # Cached: the same few thousand name words are compared over and over
    # when every author record is checked against every profile.
    if a == b:
        return True
    if len(a) < 4 or len(b) < 4 or a[0] != b[0]:
        return False
    m = SequenceMatcher(None, a, b)
    return m.real_quick_ratio() >= 0.7 and m.quick_ratio() >= 0.7 and m.ratio() >= 0.7


def _initial_of(letter: str, word: str) -> bool:
    return len(letter) == 1 and word.startswith(letter)


def _pair(x: str, y: str) -> bool:
    return _same_word(x, y) or _initial_of(x, y) or _initial_of(y, x)


def printed_name_fits(printed: str, profile: str) -> bool:
    p, f = words(printed), words(profile)
    if not p or not f:
        return False
    if _compact(p) == _compact(f):
        return True
    used: set[int] = set()
    agreed: list[str] = []
    extra: list[str] = []
    for w in p:
        j = next((k for k, x in enumerate(f) if k not in used and _pair(w, x)), None)
        if j is None:
            extra.append(w)
            continue
        used.add(j)
        full = w if len(w) > 1 else f[j]
        if len(w) > 1 and len(f[j]) > 1:
            agreed.append(full)
    missing = [x for k, x in enumerate(f) if k not in used]
    distinctive = [w for w in agreed if w not in COMMON]
    if extra and missing:
        return len(extra) == 1 and len(distinctive) >= 2
    if extra:
        return len(extra) == 1 and len(distinctive) >= 1
    if distinctive or len(agreed) >= 3:
        return True
    # "A. Jamil" for "Asma Jamil": every word accounted for and the
    # initial stands for the first name.
    return len(p[0]) == 1 and len(f) == len(p) and f[0].startswith(p[0])
