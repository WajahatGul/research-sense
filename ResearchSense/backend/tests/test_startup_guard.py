"""The developer shortcut cannot reach a public site."""

import pytest

from app.core.config import check_safe_to_start, is_local_deployment


def test_local_origins_are_recognised():
    for origin in (
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://portal.localhost",
        "http://researchsense.test",
    ):
        assert is_local_deployment(origin), origin
    assert not is_local_deployment("https://research-sense.vercel.app")


def test_refuses_to_start_publicly_with_the_shortcut():
    with pytest.raises(RuntimeError, match="DEV_ORCID"):
        check_safe_to_start(
            dev_orcid="0000-0002-1825-0097", origin="https://research-sense.vercel.app"
        )


def test_starts_locally_with_it_or_anywhere_without_it():
    check_safe_to_start(dev_orcid="0000-0002-1825-0097", origin="http://localhost:5173")
    check_safe_to_start(dev_orcid="", origin="https://research-sense.vercel.app")
