"""Issue 406 — a password found in data breaches is refused (ASVS 6.2.4), and so is one holding the member's
own login or name (6.2.11); a long, unusual one passes. The list ships with the code (no outside call)."""

import pytest

from portalab.modules.identity.services.credentials import (
    PasswordRejected,
    check_password_policy,
    common_passwords,
)
from portalab.modules.identity.settings import PasswordPolicy

pytestmark = pytest.mark.unit
POLICY = PasswordPolicy(min_length=8)


def test_the_list_ships_with_the_code() -> None:
    assert len(common_passwords()) > 40_000 and "password1234" in common_passwords()


@pytest.mark.parametrize("password", ["password1234", "PassWord1234", "iloveyou123", "qwertyuiop"])
def test_a_breached_password_is_refused(password: str) -> None:
    with pytest.raises(PasswordRejected) as refused:
        check_password_policy(password, POLICY)
    assert refused.value.code == "user.password_common"


def test_a_password_holding_the_login_or_name_is_refused() -> None:
    with pytest.raises(PasswordRejected) as refused:
        check_password_policy("my-Grace-forever-77", POLICY, personal=("grace", "Grace Hopper"))
    assert refused.value.code == "user.password_personal"
    check_password_policy("violet tram ladder 41", POLICY, personal=("grace", "Grace Hopper", "ab"))
