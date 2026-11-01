"""Safety net: the test suite may only ever touch a local database whose name ends in _test."""

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1"})


class UnsafeTestDatabaseError(RuntimeError):
    """Raised before any statement runs when TEST_DATABASE_URL is not clearly a test database."""


def assert_safe_test_database(url: str | None, extra_hosts: frozenset[str] = frozenset()) -> None:
    """Refuse anything but a local database whose name ends in _test.

    `extra_hosts` is an explicit opt-in for a test database that is only reachable under a
    service name (the Compose `db-test` container). It never relaxes the name rule.
    """
    if not url:
        raise UnsafeTestDatabaseError("TEST_DATABASE_URL is not set")
    try:
        parsed = make_url(url)
    except ArgumentError as exc:
        raise UnsafeTestDatabaseError("TEST_DATABASE_URL is not a valid database URL") from exc

    # A socket path (for example /cloudsql/...) leaves the host empty, so it is refused here.
    if parsed.host not in (ALLOWED_HOSTS | extra_hosts) or parsed.query.get("host"):
        raise UnsafeTestDatabaseError(
            f"refusing to run: host {parsed.host!r} is not an allowed test database host"
        )
    if not (parsed.database or "").endswith("_test"):
        raise UnsafeTestDatabaseError(
            f"refusing to run: database {parsed.database!r} does not end in _test"
        )
