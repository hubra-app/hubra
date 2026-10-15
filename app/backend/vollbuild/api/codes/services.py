"""Code service — business logic decoupled from HTTP layer."""

from __future__ import annotations

from sqlalchemy import select

from vollbuild.api.utils import log_audit
from vollbuild.core.crypto import encrypt_code
from vollbuild.core.errors import raise_error
from vollbuild.core.extensions import db
from vollbuild.core.models.code import Code


class CodeService:
    """Operations on a single code."""

    @staticmethod
    def get_by_id(id: int) -> Code:
        code = db.session.scalar(select(Code).where(Code.id == id))
        if code is None:
            raise_error(404, "NOT_FOUND", f"Code {id} not found")
        return code  # type: ignore[return-value]

    @staticmethod
    def update(code: Code, data: dict, actor_id: int) -> Code:
        if "name" in data:
            code.name = data["name"]
        if "code" in data:
            code.code = encrypt_code(data["code"])
        if "description" in data:
            code.description = data["description"]
        if "is_active" in data:
            code.is_active = data["is_active"]

        code.updated_by_id = actor_id

        log_audit(
            actor_id=actor_id,
            action="update_code",
            target_type="Code",
            target_id=code.id,
            target_label=code.name,
        )

        return code

    @staticmethod
    def delete(code: Code) -> None:
        db.session.delete(code)


class CodesService:
    """Operations on the codes collection."""

    @staticmethod
    def list() -> list[Code]:
        result = db.session.scalars(select(Code).order_by(Code.name))
        return list(result.all())

    @staticmethod
    def create(data: dict, actor_id: int) -> Code:
        code = Code(
            name=data["name"],
            code=encrypt_code(data["code"]),
            description=data.get("description"),
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )
        db.session.add(code)

        log_audit(
            actor_id=actor_id,
            action="create_code",
            target_type="Code",
            target_id=code.id,
            target_label=code.name,
        )

        return code
