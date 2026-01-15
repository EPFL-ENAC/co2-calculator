from app.models.user import GlobalScope, Role, RoleName, RoleScope, UserBase


def test_roles_serialization_and_deserialization():
    roles = [
        Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope()),
        Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345")),
    ]
    user = UserBase(email="test@epfl.ch", user_id=None)
    user.roles = roles  # This sets roles_raw

    # Check serialization: roles should be dicts
    serialized = user.model_dump()["roles_raw"]
    assert all(isinstance(r, dict) for r in serialized)
    assert serialized[0]["role"] == RoleName.CO2_SUPERADMIN
    assert serialized[0]["on"]["scope"] == "global"
    assert serialized[1]["on"]["unit"] == "12345"

    # Check deserialization: roles should be Role objects
    user2 = UserBase.model_validate(
        {"roles_raw": serialized, "email": "test@epfl.ch", "user_id": None}
    )
    assert all(isinstance(r, Role) for r in user2.roles)
    assert user2.roles[0].role == RoleName.CO2_SUPERADMIN
    assert isinstance(user2.roles[0].on, GlobalScope)
    assert user2.roles[1].on.unit == "12345"
