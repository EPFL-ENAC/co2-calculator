from app.models.user import GlobalScope, Role, RoleName, RoleScope, UserBase


def test_roles_serialization_and_deserialization():
    roles = [
        Role(role=RoleName.CO2_BACKOFFICE_ADMIN, on=GlobalScope()),
        Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="12345")),
    ]
    user = UserBase(roles=roles, email="test@epfl.ch", sciper=None)

    # Check serialization: roles should be dicts
    serialized = user.model_dump()["roles"]
    assert all(isinstance(r, dict) for r in serialized)
    assert serialized[0]["role"] == RoleName.CO2_BACKOFFICE_ADMIN
    assert serialized[0]["on"]["scope"] == "global"
    assert serialized[1]["on"]["unit"] == "12345"

    # Check deserialization: roles should be Role objects
    user2 = UserBase.model_validate(
        {"roles": serialized, "email": "test@epfl.ch", "sciper": None}
    )
    assert all(isinstance(r, Role) for r in user2.roles)
    assert user2.roles[0].role == RoleName.CO2_BACKOFFICE_ADMIN
    assert isinstance(user2.roles[0].on, GlobalScope)
    assert user2.roles[1].on.unit == "12345"
