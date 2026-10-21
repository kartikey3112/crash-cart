import pytest
from pydantic import ValidationError

from app.bugs import BUG_DESCRIPTIONS, Bug, UnknownBugError, parse_bug_header
from app.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.feature("bug-switches")]

TOKEN = "secret"


def test_header_ignored_without_token():
    """Bug names without a token enable nothing, so the public store can't be broken."""
    assert parse_bug_header("cart_rounding", None, TOKEN) == frozenset()


def test_header_ignored_with_wrong_token():
    """A wrong token enables nothing."""
    assert parse_bug_header("cart_rounding", "guess", TOKEN) == frozenset()


def test_valid_token_enables_listed_bugs():
    """With the right token, every listed switch is enabled (whitespace tolerated)."""
    bugs = parse_bug_header(" cart_rounding , order_idor ", TOKEN, TOKEN)
    assert bugs == {Bug.CART_ROUNDING, Bug.ORDER_IDOR}


def test_unknown_bug_name_is_an_error():
    """A typo in a switch name fails loudly instead of silently running bug-free."""
    with pytest.raises(UnknownBugError):
        parse_bug_header("cart_rounding,cart_rounding_typo", TOKEN, TOKEN)


def test_every_bug_is_documented():
    """Every switch has a description (the dashboard and docs list them)."""
    assert set(BUG_DESCRIPTIONS) == set(Bug)


@pytest.mark.feature("config")
def test_production_refuses_dev_secrets():
    """Production mode won't start while any secret still has its dev default."""
    with pytest.raises(ValidationError, match="dev defaults"):
        Settings(_env_file=None, environment="production", jwt_secret="j" * 32)


@pytest.mark.feature("config")
def test_production_starts_with_real_secrets():
    """Production mode starts once every secret is overridden."""
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="j" * 32,
        test_token="t",
        admin_password="p",
    )
    assert settings.environment == "production"


@pytest.mark.feature("config")
def test_production_rejects_short_jwt_secret():
    """Production needs a JWT secret of at least 32 characters (256 bits for HS256)."""
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="j" * 31,
            test_token="t",
            admin_password="p",
        )


@pytest.mark.feature("config")
def test_cors_origins_parsed_from_comma_list():
    """CORS origins come from one comma-separated env var."""
    settings = Settings(_env_file=None, cors_origins="https://a.example, https://b.example")
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]
