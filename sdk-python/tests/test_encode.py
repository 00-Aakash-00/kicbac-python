from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from urllib.parse import parse_qs

import pytest

from kicbac._encode import (
    encode_amount,
    encode_billing,
    encode_bool,
    encode_csv,
    encode_date,
    encode_datetime,
    encode_dup_seconds,
    encode_shipping,
    form_encode,
    merchant_defined_fields,
    put,
)
from kicbac.errors import InvalidRequestError


class TestFormEncode:
    def test_reserved_characters_round_trip(self):
        params = {"a&b": "x=y&z", "plus": "1+1", "pct": "100%"}
        body = form_encode(params)
        assert parse_qs(body.decode(), keep_blank_values=True) == {
            "a&b": ["x=y&z"],
            "plus": ["1+1"],
            "pct": ["100%"],
        }

    def test_unicode_is_utf8_percent_encoded(self):
        body = form_encode({"order_description": "Müller & Söhne — 日本語"})
        assert b"M%C3%BCller" in body
        parsed = parse_qs(body.decode(), keep_blank_values=True)
        assert parsed["order_description"] == ["Müller & Söhne — 日本語"]

    def test_spaces_and_empty_values(self):
        body = form_encode({"order_description": "two words", "orderid": ""})
        assert body == b"order_description=two+words&orderid="

    def test_body_is_ascii_bytes(self):
        assert form_encode({"k": "v"}).decode("ascii") == "k=v"


class TestEncodeAmount:
    @pytest.mark.parametrize("value", ["19.99", "0.01", "1", "12345678.99", "5.5"])
    def test_valid_strings_pass_through(self, value):
        assert encode_amount(value) == value

    def test_decimal_quantized_to_two_places(self):
        assert encode_amount(Decimal("19.9")) == "19.90"
        assert encode_amount(Decimal("7")) == "7.00"

    def test_decimal_with_sub_cent_precision_rejected(self):
        with pytest.raises(InvalidRequestError, match="2 decimal places"):
            encode_amount(Decimal("19.999"))

    @pytest.mark.parametrize(
        "value", ["49.999", "-1.00", "1,000.00", "1.2.3", "", "abc", "123456789.00", "+1.00"]
    )
    def test_invalid_strings_rejected(self, value):
        with pytest.raises(InvalidRequestError):
            encode_amount(value)

    @pytest.mark.parametrize("value", [19.99, 1, None])
    def test_non_string_non_decimal_rejected_with_type_error(self, value):
        with pytest.raises(TypeError, match="str or Decimal"):
            encode_amount(value)

    def test_zero_rejected_unless_allowed(self):
        with pytest.raises(InvalidRequestError, match="greater than zero"):
            encode_amount("0.00")
        assert encode_amount("0.00", allow_zero=True) == "0.00"

    def test_negative_decimal_rejected(self):
        with pytest.raises(InvalidRequestError):
            encode_amount(Decimal("-5.00"))


class TestScalarEncoders:
    def test_bool(self):
        assert encode_bool(True) == "true"
        assert encode_bool(False) == "false"

    def test_date_from_object_and_string(self):
        assert encode_date(date(2026, 1, 5), field="start_date") == "20260105"
        assert encode_date("20260105", field="start_date") == "20260105"
        with pytest.raises(InvalidRequestError, match="start_date"):
            encode_date("2026-01-05", field="start_date")

    def test_datetime_formats(self):
        assert (
            encode_datetime(datetime(2026, 1, 5, 13, 30, 9), field="start_date") == "20260105133009"
        )
        assert encode_datetime(date(2026, 1, 5), field="start_date") == "20260105000000"
        assert encode_datetime("20260105133009", field="start_date") == "20260105133009"
        assert encode_datetime("20260105", field="start_date") == "20260105000000"
        with pytest.raises(InvalidRequestError):
            encode_datetime("Jan 5", field="start_date")

    def test_csv(self):
        assert encode_csv("complete", field="condition") == "complete"
        assert encode_csv(["pending", "complete"], field="condition") == "pending,complete"
        with pytest.raises(InvalidRequestError, match="empty"):
            encode_csv([], field="condition")

    def test_dup_seconds(self):
        assert encode_dup_seconds(0) == "0"
        assert encode_dup_seconds(7862400) == "7862400"
        with pytest.raises(InvalidRequestError):
            encode_dup_seconds(7862401)
        with pytest.raises(InvalidRequestError):
            encode_dup_seconds(-1)
        with pytest.raises(TypeError):
            encode_dup_seconds(True)

    def test_merchant_defined_fields(self):
        assert merchant_defined_fields({1: "a", 20: "b"}) == {
            "merchant_defined_field_1": "a",
            "merchant_defined_field_20": "b",
        }
        with pytest.raises(InvalidRequestError, match="out of range"):
            merchant_defined_fields({21: "x"})
        with pytest.raises(InvalidRequestError, match="out of range"):
            merchant_defined_fields({0: "x"})

    def test_put_drops_none(self):
        params: dict[str, str] = {}
        put(params, "kept", "v")
        put(params, "dropped", None)
        assert params == {"kept": "v"}


class TestAddressEncoders:
    def test_billing_passthrough(self):
        assert encode_billing({"first_name": "Jane", "zip": "60601"}) == {
            "first_name": "Jane",
            "zip": "60601",
        }

    def test_billing_unknown_key_rejected(self):
        with pytest.raises(InvalidRequestError, match="unknown billing field"):
            encode_billing({"postal_code": "60601"})  # type: ignore[typeddict-unknown-key]

    def test_shipping_mapped_to_gateway_names(self):
        assert encode_shipping({"first_name": "Jane", "address1": "1 Main St", "zip": "60601"}) == {
            "shipping_firstname": "Jane",
            "shipping_address1": "1 Main St",
            "shipping_zip": "60601",
        }

    def test_shipping_unknown_key_rejected(self):
        with pytest.raises(InvalidRequestError, match="unknown shipping field"):
            encode_shipping({"phone": "555"})  # type: ignore[typeddict-unknown-key]
