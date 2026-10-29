"""Invoice mails go out only for invoices that were committed."""

from unittest.mock import patch

from sqlalchemy import select

from tests.finance.conftest import billable_tier_db  # noqa: F401


def test_no_mail_for_a_rolled_back_invoice(app, billable_tier_db, db):  # noqa: F811
    from hubra.core.models.finance import Invoice
    from hubra.core.models.member import Member
    from hubra.core.models.user import User
    from hubra.core.tasks import finance_tasks

    user = User(email="carol@test.ch", first_name="Carol", last_name="X")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    second = Member(
        user_id=user.id, status="active", tier_id=billable_tier_db["billable_tier"].id
    )
    db.session.add(second)
    db.session.commit()
    first = billable_tier_db["member_billed"]
    real = finance_tasks.calculate_invoice_amount

    def fails_for_second(member, tier, day):
        if member.id == second.id:
            raise RuntimeError("boom")
        return real(member, tier, day)

    with patch("hubra.core.tasks.email_tasks.send_email_task.delay") as delay:
        with patch.object(finance_tasks, "calculate_invoice_amount", fails_for_second):
            try:
                finance_tasks.generate_invoices_task.run()
            except RuntimeError:
                db.session.rollback()
        finance_tasks.generate_invoices_task.run()

    to_first = [c for c in delay.call_args_list if c.kwargs["to_email"] == first.email]
    invoices = db.session.scalars(
        select(Invoice).where(Invoice.member_id == first.id)
    ).all()
    assert len(invoices) == 1
    assert len(to_first) == 1
