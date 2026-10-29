"""GET /functions costs the same number of queries for 3 functions as for 9."""

from tests.test_list_query_counts import _add_member, _queries


def test_functions_list(client, auth_headers, db, seeded_db):
    from hubra.core.models.function import Function, FunctionHolder

    members = [_add_member(db, seeded_db["tier"], n) for n in range(9)]

    def add_functions(start, count):
        for n in range(start, start + count):
            fn = Function(name=f"Fn {n}", max_holders=2)
            db.session.add(fn)
            db.session.flush()
            db.session.add(FunctionHolder(function_id=fn.id, member_id=members[n].id))
        db.session.commit()

    add_functions(0, 3)
    before, _ = _queries(client, db, "/api/v1/functions/")
    add_functions(3, 6)
    after, body = _queries(client, db, "/api/v1/functions/")

    assert after == before
    fn = next(f for f in body if f["name"] == "Fn 4")
    assert [h["memberName"] for h in fn["holders"]] == ["First4 Last4"]
