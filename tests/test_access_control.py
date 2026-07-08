from access_control import is_allowed_domain, is_session_expired


def test_allowed_domain_exact_match():
    assert is_allowed_domain("ezequiel@admin.com.ar") is True


def test_allowed_domain_case_insensitive():
    assert is_allowed_domain("ezequiel@ADMIN.COM.AR") is True


def test_rejects_lookalike_domain():
    # "evil-admin.com.ar" no es "admin.com.ar" — comparación debe ser exacta, no endswith/in
    assert is_allowed_domain("atacante@evil-admin.com.ar") is False


def test_rejects_subdomain_bypass():
    # un endswith(".admin.com.ar") ingenuo dejaría pasar esto; la comparación exacta lo bloquea
    assert is_allowed_domain("atacante@sub.admin.com.ar") is False


def test_rejects_other_domain():
    assert is_allowed_domain("alguien@gmail.com") is False


def test_session_not_expired_within_timeout():
    assert is_session_expired(last_activity=1000, now=1000 + 3600, timeout_seconds=7200) is False


def test_session_expired_after_timeout():
    assert is_session_expired(last_activity=1000, now=1000 + 7201, timeout_seconds=7200) is True
