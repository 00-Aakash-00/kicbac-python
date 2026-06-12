"""Gateway constants and the vendored response-code table.

The vendored table below is a copy of ``openapi/data/response-codes.json``
(source of truth shared with the Node SDK); ``tests/test_outcome.py`` asserts
they stay in sync.
"""

from __future__ import annotations

import httpx

DEFAULT_BASE_URL = "https://kicbac.transactiongateway.com"
TRANSACT_PATH = "/api/transact.php"
QUERY_PATH = "/api/query.php"

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
DEFAULT_MAX_RETRIES = 2

# Matches gateway responsetext for code-300 rejections that are credential
# failures (case-insensitive). Synced with response-codes.json.
AUTH_FAIL_PATTERN = "authentication failed|invalid (security )?key|invalid username"

# Rows: (code, text, response, outcome, error_class). outcome: "approved" |
# "declined" | "error"; error_class is None unless outcome == "error".
VENDORED_RESPONSE_CODES: tuple[tuple[int, str, int, str, str | None], ...] = (
    (100, "Transaction was approved.", 1, "approved", None),
    (200, "Transaction was declined by processor.", 2, "declined", None),
    (201, "Do not honor.", 2, "declined", None),
    (202, "Insufficient funds.", 2, "declined", None),
    (203, "Over limit.", 2, "declined", None),
    (204, "Transaction not allowed.", 2, "declined", None),
    (220, "Incorrect payment information.", 2, "declined", None),
    (221, "No such card issuer.", 2, "declined", None),
    (222, "No card number on file with issuer.", 2, "declined", None),
    (223, "Expired card.", 2, "declined", None),
    (224, "Invalid expiration date.", 2, "declined", None),
    (225, "Invalid card security code.", 2, "declined", None),
    (226, "Invalid PIN.", 2, "declined", None),
    (240, "Call issuer for further information.", 2, "declined", None),
    (250, "Pick up card.", 2, "declined", None),
    (251, "Lost card.", 2, "declined", None),
    (252, "Stolen card.", 2, "declined", None),
    (253, "Fraudulent card.", 2, "declined", None),
    (260, "Declined with further instructions available.", 2, "declined", None),
    (261, "Declined - stop all recurring payments.", 2, "declined", None),
    (262, "Declined - stop this recurring program.", 2, "declined", None),
    (263, "Declined - update cardholder data available.", 2, "declined", None),
    (264, "Declined - retry in a few days.", 2, "declined", None),
    (300, "Transaction was rejected by gateway.", 3, "error", "InvalidRequestError"),
    (301, "Rate limit exceeded.", 3, "error", "RateLimitError"),
    (400, "Transaction error returned by processor.", 3, "error", "ProcessorError"),
    (410, "Invalid merchant configuration.", 3, "error", "ProcessorError"),
    (411, "Merchant account is inactive.", 3, "error", "ProcessorError"),
    (420, "Communication error.", 3, "error", "ProcessorError"),
    (421, "Communication error with issuer.", 3, "error", "ProcessorError"),
    (430, "Duplicate transaction at processor.", 3, "error", "ProcessorError"),
    (440, "Processor format error.", 3, "error", "ProcessorError"),
    (441, "Invalid transaction information.", 3, "error", "ProcessorError"),
    (460, "Processor feature not available.", 3, "error", "ProcessorError"),
    (461, "Unsupported card type.", 3, "error", "ProcessorError"),
)

ERROR_CLASS_BY_CODE: dict[int, str] = {
    code: error_class
    for code, _text, _response, outcome, error_class in VENDORED_RESPONSE_CODES
    if outcome == "error" and error_class is not None
}
