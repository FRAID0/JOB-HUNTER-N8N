"""Opt-in policy for filling passwords on explicitly trusted job portals."""

from urllib.parse import urlparse


def get_site_password(profile: dict, page_url: str):
    """Return a password only for an exact, explicitly configured hostname."""
    hostname = (urlparse(page_url).hostname or "").lower().rstrip(".")
    if not hostname:
        return None

    site_passwords = profile.get("site_passwords", {})
    if isinstance(site_passwords, dict):
        for configured_host, password in site_passwords.items():
            if str(configured_host).lower().lstrip(".") == hostname and password:
                return str(password)

    personal_info = profile.get("personal_info", {})
    allowed_domains = profile.get("password_domains", personal_info.get("password_domains", []))
    default_password = personal_info.get("default_password")
    if default_password and hostname in {str(domain).lower().lstrip(".") for domain in allowed_domains}:
        return str(default_password)

    return None