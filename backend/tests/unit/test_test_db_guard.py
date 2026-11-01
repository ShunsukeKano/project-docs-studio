"""The test-database guard must refuse anything that is not a local database ending in _test."""

import pytest

from tests.db_guard import UnsafeTestDatabaseError, assert_safe_test_database


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@localhost:5433/docs_test",
        "postgresql+asyncpg://u:p@127.0.0.1:5432/anything_test",
    ],
)
def test_accepts_a_local_database_ending_in_test(url: str) -> None:
    assert_safe_test_database(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@localhost:5432/docs_dev",
        "postgresql+asyncpg://u:p@localhost:5432/docs",
        "postgresql+asyncpg://u:p@localhost:5432/docs_prod",
        "postgresql+asyncpg://u:p@localhost:5432/test_docs",
        "postgresql+asyncpg://u:p@localhost:5432/",
    ],
)
def test_refuses_a_name_that_does_not_end_in_test(url: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        assert_safe_test_database(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@10.1.2.3:5432/docs_test",
        "postgresql+asyncpg://u:p@db.example.com:5432/docs_test",
        "postgresql+asyncpg://u:p@localhost.evil.example:5432/docs_test",
        "postgresql+asyncpg://u:p@/docs_test?host=/cloudsql/proj:region:instance",
        "postgresql+asyncpg://u:p@/docs_test",
    ],
)
def test_refuses_a_host_that_is_not_local(url: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        assert_safe_test_database(url)


@pytest.mark.parametrize("url", [None, "", "not a url"])
def test_refuses_a_missing_or_malformed_url(url: str | None) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        assert_safe_test_database(url)


class TestExtraHosts:
    URL = "postgresql+asyncpg://u:p@db-test:5432/docs_test"

    def test_a_service_name_is_refused_unless_it_is_named_explicitly(self) -> None:
        with pytest.raises(UnsafeTestDatabaseError):
            assert_safe_test_database(self.URL)
        assert_safe_test_database(self.URL, frozenset({"db-test"}))

    def test_an_extra_host_never_relaxes_the_name_rule(self) -> None:
        url = "postgresql+asyncpg://u:p@db-test:5432/docs_prod"
        with pytest.raises(UnsafeTestDatabaseError):
            assert_safe_test_database(url, frozenset({"db-test"}))

    def test_other_hosts_stay_refused(self) -> None:
        with pytest.raises(UnsafeTestDatabaseError):
            assert_safe_test_database(
                self.URL.replace("db-test:", "prod-db:"), frozenset({"db-test"})
            )
