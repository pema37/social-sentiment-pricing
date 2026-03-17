"""
Tests for services/payment/exceptions.py

MNEE Payment Exception hierarchy tests.
Covers: MneeBaseError, MneeApiError, MneeValidationError,
        MneeConfigError, MneeNetworkError
"""

import sys
from unittest.mock import MagicMock

# Standard import isolation
for mod in ["db.session"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest

from services.payment.exceptions import (
    MneeApiError,
    MneeBaseError,
    MneeConfigError,
    MneeNetworkError,
    MneeValidationError,
)


# ──────────────────────────────────────────────
# MneeBaseError
# ──────────────────────────────────────────────
class TestMneeBaseError:
    """Tests for the base MNEE exception class."""

    def test_inherits_from_exception(self):
        assert issubclass(MneeBaseError, Exception)

    def test_message_only(self):
        err = MneeBaseError("something broke")
        assert err.message == "something broke"
        assert err.code is None
        assert err.details == {}
        assert str(err) == "something broke"

    def test_with_code(self):
        err = MneeBaseError("fail", code="ERR_001")
        assert err.code == "ERR_001"

    def test_with_details(self):
        details = {"key": "value", "count": 42}
        err = MneeBaseError("fail", details=details)
        assert err.details == details

    def test_details_default_empty_dict(self):
        err = MneeBaseError("fail", details=None)
        assert err.details == {}

    def test_all_params(self):
        err = MneeBaseError("msg", code="C1", details={"a": 1})
        assert err.message == "msg"
        assert err.code == "C1"
        assert err.details == {"a": 1}

    def test_catchable_as_exception(self):
        with pytest.raises(Exception):
            raise MneeBaseError("test")

    def test_catchable_as_self(self):
        with pytest.raises(MneeBaseError):
            raise MneeBaseError("test")

    def test_str_matches_message(self):
        err = MneeBaseError("hello world")
        assert str(err) == "hello world"

    def test_empty_message(self):
        err = MneeBaseError("")
        assert err.message == ""
        assert str(err) == ""

    def test_details_not_shared_between_instances(self):
        e1 = MneeBaseError("a")
        e2 = MneeBaseError("b")
        e1.details["x"] = 1
        assert "x" not in e2.details


# ──────────────────────────────────────────────
# MneeApiError
# ──────────────────────────────────────────────
class TestMneeApiError:
    """Tests for MNEE API error."""

    def test_inherits_from_base(self):
        assert issubclass(MneeApiError, MneeBaseError)

    def test_default_values(self):
        err = MneeApiError("api fail")
        assert err.message == "api fail"
        assert err.status_code is None
        assert err.response is None
        assert err.code == "MNEE_API_ERROR"
        assert err.details == {"status_code": None, "response": None}

    def test_with_status_code(self):
        err = MneeApiError("not found", status_code=404)
        assert err.status_code == 404
        assert err.details["status_code"] == 404

    def test_with_response(self):
        resp = {"error": "invalid_token", "message": "Token expired"}
        err = MneeApiError("auth fail", response=resp)
        assert err.response == resp
        assert err.details["response"] == resp

    def test_all_params(self):
        resp = {"ok": False}
        err = MneeApiError("server error", status_code=500, response=resp)
        assert err.message == "server error"
        assert err.status_code == 500
        assert err.response == resp
        assert err.code == "MNEE_API_ERROR"
        assert err.details == {"status_code": 500, "response": resp}

    def test_catchable_as_base(self):
        with pytest.raises(MneeBaseError):
            raise MneeApiError("fail")

    def test_catchable_as_exception(self):
        with pytest.raises(Exception):
            raise MneeApiError("fail")

    def test_str_matches_message(self):
        err = MneeApiError("bad request", status_code=400)
        assert str(err) == "bad request"

    def test_status_code_zero(self):
        err = MneeApiError("weird", status_code=0)
        assert err.status_code == 0

    def test_empty_response_dict(self):
        err = MneeApiError("empty", response={})
        assert err.response == {}
        assert err.details["response"] == {}


# ──────────────────────────────────────────────
# MneeValidationError
# ──────────────────────────────────────────────
class TestMneeValidationError:
    """Tests for MNEE validation error."""

    def test_inherits_from_base(self):
        assert issubclass(MneeValidationError, MneeBaseError)

    def test_default_values(self):
        err = MneeValidationError("invalid input")
        assert err.message == "invalid input"
        assert err.field is None
        assert err.code == "MNEE_VALIDATION_ERROR"
        assert err.details == {"field": None}

    def test_with_field(self):
        err = MneeValidationError("bad amount", field="amount")
        assert err.field == "amount"
        assert err.details["field"] == "amount"

    def test_catchable_as_base(self):
        with pytest.raises(MneeBaseError):
            raise MneeValidationError("bad")

    def test_str_matches_message(self):
        err = MneeValidationError("wrong format", field="email")
        assert str(err) == "wrong format"

    def test_field_empty_string(self):
        err = MneeValidationError("err", field="")
        assert err.field == ""
        assert err.details["field"] == ""

    def test_code_is_correct(self):
        err = MneeValidationError("x")
        assert err.code == "MNEE_VALIDATION_ERROR"


# ──────────────────────────────────────────────
# MneeConfigError
# ──────────────────────────────────────────────
class TestMneeConfigError:
    """Tests for MNEE configuration error."""

    def test_inherits_from_base(self):
        assert issubclass(MneeConfigError, MneeBaseError)

    def test_default_values(self):
        err = MneeConfigError("missing config")
        assert err.message == "missing config"
        assert err.missing_key is None
        assert err.code == "MNEE_CONFIG_ERROR"
        assert err.details == {"missing_key": None}

    def test_with_missing_key(self):
        err = MneeConfigError("key not found", missing_key="MNEE_API_KEY")
        assert err.missing_key == "MNEE_API_KEY"
        assert err.details["missing_key"] == "MNEE_API_KEY"

    def test_catchable_as_base(self):
        with pytest.raises(MneeBaseError):
            raise MneeConfigError("bad config")

    def test_str_matches_message(self):
        err = MneeConfigError("no key", missing_key="SECRET")
        assert str(err) == "no key"

    def test_code_is_correct(self):
        err = MneeConfigError("x")
        assert err.code == "MNEE_CONFIG_ERROR"

    def test_missing_key_empty_string(self):
        err = MneeConfigError("err", missing_key="")
        assert err.missing_key == ""


# ──────────────────────────────────────────────
# MneeNetworkError
# ──────────────────────────────────────────────
class TestMneeNetworkError:
    """Tests for MNEE network error."""

    def test_inherits_from_base(self):
        assert issubclass(MneeNetworkError, MneeBaseError)

    def test_default_values(self):
        err = MneeNetworkError("timeout")
        assert err.message == "timeout"
        assert err.original_error is None
        assert err.code == "MNEE_NETWORK_ERROR"
        assert err.details == {"original_error": None}

    def test_with_original_error(self):
        orig = ConnectionError("refused")
        err = MneeNetworkError("connection failed", original_error=orig)
        assert err.original_error is orig
        assert err.details["original_error"] == "refused"

    def test_original_error_str_conversion(self):
        orig = TimeoutError("timed out after 30s")
        err = MneeNetworkError("timeout", original_error=orig)
        assert err.details["original_error"] == "timed out after 30s"

    def test_original_error_none_in_details(self):
        err = MneeNetworkError("fail", original_error=None)
        assert err.details["original_error"] is None

    def test_catchable_as_base(self):
        with pytest.raises(MneeBaseError):
            raise MneeNetworkError("net fail")

    def test_str_matches_message(self):
        err = MneeNetworkError("dns fail")
        assert str(err) == "dns fail"

    def test_code_is_correct(self):
        err = MneeNetworkError("x")
        assert err.code == "MNEE_NETWORK_ERROR"

    def test_preserves_original_exception_reference(self):
        orig = OSError("socket closed")
        err = MneeNetworkError("lost connection", original_error=orig)
        assert err.original_error is orig
        assert isinstance(err.original_error, OSError)

    def test_complex_original_error(self):
        inner = ValueError("bad value")
        outer = RuntimeError("wrapper")
        outer.__cause__ = inner
        err = MneeNetworkError("chain", original_error=outer)
        assert err.original_error is outer
        assert "wrapper" in err.details["original_error"]


# ──────────────────────────────────────────────
# Cross-cutting: Exception Hierarchy
# ──────────────────────────────────────────────
class TestExceptionHierarchy:
    """Tests verifying the full exception hierarchy works correctly."""

    def test_all_subclass_base(self):
        for cls in [MneeApiError, MneeValidationError, MneeConfigError, MneeNetworkError]:
            assert issubclass(cls, MneeBaseError), f"{cls.__name__} should subclass MneeBaseError"

    def test_all_subclass_exception(self):
        for cls in [MneeApiError, MneeValidationError, MneeConfigError, MneeNetworkError]:
            assert issubclass(cls, Exception), f"{cls.__name__} should subclass Exception"

    def test_catch_all_with_base(self):
        """A single except MneeBaseError catches all MNEE exceptions."""
        errors = [
            MneeApiError("a", status_code=500),
            MneeValidationError("b", field="x"),
            MneeConfigError("c", missing_key="k"),
            MneeNetworkError("d", original_error=OSError("e")),
        ]
        for error in errors:
            with pytest.raises(MneeBaseError):
                raise error

    def test_each_has_unique_code(self):
        codes = [
            MneeApiError("a").code,
            MneeValidationError("b").code,
            MneeConfigError("c").code,
            MneeNetworkError("d").code,
        ]
        assert len(set(codes)) == 4, "Each exception type should have a unique code"

    def test_base_error_does_not_catch_unrelated(self):
        with pytest.raises(ValueError):
            raise ValueError("not mnee")

    def test_isinstance_checks(self):
        err = MneeApiError("test")
        assert isinstance(err, MneeApiError)
        assert isinstance(err, MneeBaseError)
        assert isinstance(err, Exception)
        assert not isinstance(err, MneeValidationError)
