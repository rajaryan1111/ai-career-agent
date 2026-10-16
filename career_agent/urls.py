"""Validation and redaction for untrusted public links.

Manual job entry is the only place where this project accepts a URL from an untrusted
source: the source listing URL and the employer application URL are validated, stored,
displayed, exported, and later handed to whatever fetches or verifies them. These helpers
keep that boundary honest — only clearly public HTTP(S) addresses are accepted, and
credentials are never shown back to the user.

Concept adapted from Agent-Reach's untrusted-URL helpers (MIT License, Copyright (c) 2025
Agent Eyes): https://github.com/Panniantong/Agent-Reach, ``agent_reach/utils/url.py`` and
``agent_reach/utils/text.py``. Reimplemented here in this project's own standard-library
code, narrowed to what this project actually needs.

Scope and honest limits — read before reusing this for fetching:

* Only the *literal* host is inspected. There is no DNS resolution, no connection, no
  redirect following, and no fetch in this module, so **this is not SSRF protection**. A
  hostname that passes can still resolve to a private address (DNS rebinding), and a
  permitted URL can still redirect anywhere.
* Any future fetcher must resolve and connect consistently, re-validate every redirect hop,
  and apply its own response-size and time limits. Until it does, no part of this project
  may claim SSRF protection.
* Validation is intentionally conservative for a job-listing field: an intranet-style
  single-label host such as ``https://careers/`` is refused with an actionable message.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit

_ALLOWED_SCHEMES = frozenset({"http", "https"})

#: Host names that never identify a public job listing (local, cloud-metadata, internal).
_BLOCKED_HOSTS = frozenset(
    {
        "home.arpa",
        "instance-data",
        "internal",
        "ip6-localhost",
        "ip6-loopback",
        "lan",
        "local",
        "localdomain",
        "localhost",
        "metadata.google.internal",
    }
)
_BLOCKED_SUFFIXES = (
    ".home.arpa",
    ".internal",
    ".lan",
    ".local",
    ".localdomain",
    ".localhost",
)

_SCHEME_MESSAGE = "{label} must start with http:// or https://."
_PUBLIC_MESSAGE = (
    "{label} must be a public web address; credentials, localhost, private, and internal "
    "hosts are not accepted."
)

_USERINFO_IN_URL_RE = re.compile(r"([A-Za-z][A-Za-z0-9+.\-]{0,19}://)[^/\s@]+@")
_BARE_USERINFO_RE = re.compile(r"(?<![A-Za-z0-9._%+\-])[^:/\s@]+:[^/\s@]+@(?=[A-Za-z0-9.\-\[ ])")
_SECRET_QUERY_RE = re.compile(
    r"([?&#](?:"
    r"access[_-]?token|auth[_-]?token|token|bearer|"
    r"api[_-]?key|key|password|passwd|secret|"
    r"signature|sig|session(?:id)?|cookie|credential"
    r")=)[^&#\s]*",
    re.IGNORECASE,
)


def _literal_ip_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse canonical and legacy IPv4 literal spellings without touching DNS.

    ``127.1``, ``2130706433`` and ``0x7f.0.0.1`` all reach loopback, so they are parsed
    here rather than treated as ordinary host names.
    """
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    try:
        packed = socket.inet_aton(host)
    except OSError:
        return None
    return ipaddress.IPv4Address(packed)


def _host_is_public(host: str) -> bool:
    if not host or "%" in host or host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_SUFFIXES):
        return False
    literal = _literal_ip_address(host)
    if literal is not None:
        return literal.is_global
    # A public host must be dotted (fully qualified); an intranet-style single label is not.
    return "." in host


def validate_public_http_url(url: str, *, label: str = "URL") -> str:
    """Return ``url`` when it is a public HTTP(S) address, otherwise raise ``ValueError``.

    The returned value is the trimmed input; this function never rewrites the URL, so stored
    values are not silently changed. ``label`` names the field in the error message because
    those messages are shown to the user.
    """
    candidate = str(url or "").strip()
    if not candidate or "://" not in candidate or candidate.split("://", 1)[0].casefold() not in _ALLOWED_SCHEMES:
        raise ValueError(_SCHEME_MESSAGE.format(label=label))
    if (
        "\\" in candidate
        or any(character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F for character in candidate)
    ):
        raise ValueError(_PUBLIC_MESSAGE.format(label=label))

    try:
        parsed = urlsplit(candidate)
        host = (parsed.hostname or "").casefold().rstrip(".")
        # Accessing .port is what rejects malformed or out-of-range authorities.
        _ = parsed.port
    except (TypeError, ValueError):
        raise ValueError(_PUBLIC_MESSAGE.format(label=label)) from None

    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.scheme.casefold() not in _ALLOWED_SCHEMES
        or not _host_is_public(host)
    ):
        raise ValueError(_PUBLIC_MESSAGE.format(label=label))
    return candidate


def is_public_http_url(url: str) -> bool:
    """True when :func:`validate_public_http_url` accepts ``url``."""
    try:
        validate_public_http_url(url)
    except ValueError:
        return False
    return True


def redact_url_credentials(text: object) -> str:
    """Redact URL userinfo and sensitive query/fragment values from text meant for display.

    Display only: this never mutates stored data, so records written before validation was
    introduced are shown safely rather than rewritten. Redaction is intentionally aggressive —
    hiding a harmless lookalike is preferable to echoing a credential.
    """
    scrubbed = _USERINFO_IN_URL_RE.sub(r"\1***@", str(text))
    scrubbed = _BARE_USERINFO_RE.sub("***@", scrubbed)
    return _SECRET_QUERY_RE.sub(r"\1***", scrubbed)
