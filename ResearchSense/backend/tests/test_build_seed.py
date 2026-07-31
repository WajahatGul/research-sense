from scripts.build_seed import FACULTY_PER_DEPT, sample_faculty


def _rec(name, campus="Karachi", dept="Psychology", desig="Lecturer", areas="x"):
    return {
        "name": name,
        "campus": campus,
        "department": dept,
        "designation": desig,
        "areas": areas,
    }


def test_cap_respected_per_campus_department_group():
    recs = [_rec(f"P{i}") for i in range(20)]
    out = sample_faculty(recs, cap=12)
    assert len(out) == 12


def test_groups_are_independent():
    recs = [_rec(f"A{i}", dept="Law") for i in range(15)] + [
        _rec(f"B{i}", dept="Psychology") for i in range(15)
    ]
    out = sample_faculty(recs, cap=12)
    assert len(out) == 24


def test_prefers_faculty_with_areas_then_seniority():
    recs = [
        _rec("NoAreas Prof", desig="Professor", areas=""),
        _rec("Areas Lect", desig="Lecturer", areas="Clinical Psychology"),
        _rec("Areas Prof", desig="Professor", areas="Neuropsychology"),
    ]
    out = sample_faculty(recs, cap=2)
    names = [r["name"] for r in out]
    assert names == ["Areas Prof", "Areas Lect"]


def test_none_cap_returns_everyone():
    recs = [_rec(f"P{i}") for i in range(30)]
    assert len(sample_faculty(recs, cap=None)) == 30


def test_default_cap_is_twelve():
    assert FACULTY_PER_DEPT == 12
