"""A club's translation ETag follows the platform's texts too."""

from unittest.mock import patch

from hubra.api.i18n import services


class _Redis:
    def __init__(self, data):
        self.data = data

    def mget(self, keys):
        return [self.data.get(k) for k in keys]


def _etag(club, data):
    with (
        patch.object(services, "_get_redis_client", return_value=_Redis(data)),
        patch.object(services, "_club", return_value=club),
    ):
        return services.get_etag("de-CH")


def test_club_etag_changes_with_a_platform_edit():
    before = _etag(7, {"i18n:version:7:de-CH": b"3", "i18n:version:0:de-CH": b"5"})
    after = _etag(7, {"i18n:version:7:de-CH": b"3", "i18n:version:0:de-CH": b"6"})
    assert before != after
    assert _etag(7, {"i18n:version:0:de-CH": b"6"}) == '"0.6"'


def test_platform_etag_and_unset_versions():
    assert _etag(0, {"i18n:version:0:de-CH": b"6"}) == '"6"'
    assert _etag(7, {}) is None
