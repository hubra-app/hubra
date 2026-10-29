"""Without a mail domain, no club address is made (it would end in a bare '@')."""

from hubra.core.models.function import Function
from hubra.core.models.group import Group
from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.services.managed_mail import (
    auto_create_mma_for_function,
    auto_create_mma_for_group,
)
from tests.helpers import patch_mail_domain


def test_no_addresses_without_a_mail_domain(db, seeded_db):
    group = Group(name="Holzwerkstatt")
    fn = Function(name="Kassier")
    db.session.add_all([group, fn])
    db.session.commit()
    with patch_mail_domain(""):
        assert auto_create_mma_for_group(group.id) is None
        assert auto_create_mma_for_function(fn.id) is None
    assert db.session.query(ManagedMailAddress).count() == 0

    with patch_mail_domain("club.ch"):
        addr = auto_create_mma_for_group(group.id)
    assert addr is not None and addr.address.endswith("@club.ch")
