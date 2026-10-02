import pytest

from backend.services.source_quality import TIER_RANK, domain_of, is_excluded, reliability


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://WWW.CDC.GOV/page", "cdc.gov"),
        ("https://en.wikipedia.org:443/page", "en.wikipedia.org"),
        ("https://user:password@example.com/a", "example.com"),
        ("relative", ""),
    ],
)
def test_domain_of(url, expected):
    assert domain_of(url) == expected


@pytest.mark.parametrize(
    "domain,tier",
    [
        ("snopes.com", "factchecker"),
        ("www.factcheck.afp.com", "factchecker"),
        ("data.cdc.gov", "high"),
        ("foo.edu", "high"),
        ("foo.gov.uk", "high"),
        ("foo.ac.uk", "high"),
        ("foo.gc.ca", "high"),
        ("foo.gov.au", "high"),
        ("foo.europa.eu", "high"),
        ("reuters.com", "high"),
        ("nature.com", "high"),
        ("en.wikipedia.org", "medium"),
        ("www.reddit.com", "low"),
        ("author.substack.com", "low"),
        ("example.com", "unknown"),
        ("notcdc.gov.example.com", "unknown"),
        ("fakesnopes.com", "unknown"),
    ],
)
def test_reliability(domain, tier):
    assert reliability(domain) == tier


@pytest.mark.parametrize("domain", ["youtube.com", "youtu.be", "m.youtube.com", "www.youtube.com"])
def test_exclusions(domain):
    assert is_excluded(domain)
    assert not is_excluded("youtube.com.example.org")


def test_tier_order():
    assert list(TIER_RANK) == ["factchecker", "high", "medium", "unknown", "low"]
