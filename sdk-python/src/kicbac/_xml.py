"""Parsing of Query API (``query.php``) ``<nm_response>`` XML bodies."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from kicbac._constants import AUTH_FAIL_PATTERN
from kicbac.errors import APIError, AuthenticationError, InvalidRequestError

_AUTH_FAIL_RE = re.compile(AUTH_FAIL_PATTERN, re.IGNORECASE)

# Elements that repeat inside a <transaction> record; collected into lists
# under the pluralised key ("actions"/"products").
_REPEATED_TAGS = frozenset({"action", "product"})


def parse_query_records(body: str, tag: str) -> list[dict[str, object]]:
    """Extract repeating ``<tag>`` records from an ``<nm_response>`` body.

    Records are searched both as direct children of the root and one wrapper
    level down (e.g. ``<customer_vault><customer>``). An empty
    ``<nm_response/>`` yields an empty list; ``<error_response>`` raises.
    """
    root = _parse_root(body)
    # Explicit None checks: an Element with no children is falsy, so `or` would skip it.
    error = root.find("error_response")
    if error is None:
        error = root.find("./*/error_response")
    if error is not None:
        _raise_error_response(error.text or "", body)
    records = [*root.findall(tag), *root.findall(f"./*/{tag}")]
    return [_element_to_record(element) for element in records]


def _parse_root(body: str) -> ET.Element:
    if "<!DOCTYPE" in body:
        raise APIError(
            "gateway XML contains a DOCTYPE declaration; refusing to parse it "
            "(entity-expansion guard)",
            raw_body=body,
        )
    try:
        # DOCTYPE rejected above; stdlib ElementTree does not fetch external entities.
        return ET.fromstring(body)  # noqa: S314
    except ET.ParseError as exc:
        raise APIError("invalid XML from gateway", raw_body=body) from exc


def _raise_error_response(text: str, body: str) -> None:
    if _AUTH_FAIL_RE.search(text):
        raise AuthenticationError(
            f"gateway rejected the security key: {text or 'no detail provided'} — check the "
            "key in Settings > Security Keys and that it matches this environment",
            response_text=text,
            raw_body=body,
        )
    raise InvalidRequestError(
        f"query rejected by gateway: {text or 'no detail provided'}",
        response_text=text,
        raw_body=body,
    )


def _element_to_record(element: ET.Element) -> dict[str, object]:
    record: dict[str, object] = {}
    repeated: dict[str, list[dict[str, object]]] = {}
    for child in element:
        if child.tag in _REPEATED_TAGS:
            repeated.setdefault(f"{child.tag}s", []).append(_element_to_record(child))
        elif len(child):
            record[child.tag] = _element_to_record(child)
        else:
            record[child.tag] = child.text or ""
    record.update(repeated)
    return record
