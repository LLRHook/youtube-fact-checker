"""Domain-level source reliability for evidence ordering."""

from urllib.parse import urlsplit

_FACTCHECKERS = "snopes.com politifact.com factcheck.org fullfact.org factcheck.afp.com leadstories.com healthfeedback.org science.feedback.org climatefeedback.org checkyourfact.com".split()
_HIGH = "who.int cdc.gov nih.gov nature.com science.org sciencedirect.com thelancet.com nejm.org bmj.com jamanetwork.com cochranelibrary.com pubmed.ncbi.nlm.nih.gov reuters.com apnews.com bbc.com bbc.co.uk npr.org nytimes.com washingtonpost.com wsj.com ft.com economist.com theguardian.com bloomberg.com britannica.com worldbank.org imf.org oecd.org un.org pewresearch.org ourworldindata.org mayoclinic.org clevelandclinic.org nasa.gov noaa.gov".split()
_HIGH_SUFFIXES = ".gov .mil .edu .int .gov.uk .ac.uk .gc.ca .gov.au .europa.eu".split()
_MEDIUM = "wikipedia.org investopedia.com healthline.com webmd.com cnn.com cnbc.com forbes.com time.com theatlantic.com scientificamerican.com newscientist.com smithsonianmag.com nationalgeographic.com history.com statista.com axios.com politico.com vox.com".split()
_LOW = "reddit.com quora.com medium.com facebook.com x.com twitter.com tiktok.com instagram.com pinterest.com blogspot.com wordpress.com substack.com".split()
TIER_RANK = {"factchecker": 0, "high": 1, "medium": 2, "unknown": 3, "low": 4}


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def _matches(domain: str, domains: list[str]) -> bool:
    return any(domain == item or domain.endswith("." + item) for item in domains)


def reliability(domain: str) -> str:
    domain = domain.lower().removeprefix("www.")
    if _matches(domain, _FACTCHECKERS):
        return "factchecker"
    if _matches(domain, _HIGH) or any(domain.endswith(suffix) for suffix in _HIGH_SUFFIXES):
        return "high"
    if _matches(domain, _MEDIUM):
        return "medium"
    if _matches(domain, _LOW):
        return "low"
    return "unknown"


def is_excluded(domain: str) -> bool:
    return _matches(domain.lower().removeprefix("www."), ["youtube.com", "youtu.be", "m.youtube.com"])
