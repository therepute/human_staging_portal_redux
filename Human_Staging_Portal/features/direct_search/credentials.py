from typing import Dict, Optional


def normalize_domain(domain: str) -> str:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(domain if domain.startswith("http") else f"https://{domain}")
        host = parsed.netloc or parsed.path
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        parts = host.split(".")
        if len(parts) >= 2:
            host = ".".join(parts[-2:])
        return host
    except Exception:
        return domain.lower()


def find_credentials_for_publication(
    name: Optional[str],
    domain: Optional[str],
    subscription_credentials_index: Dict[str, Dict[str, str]],
    subscription_name_index: Dict[str, Dict[str, str]],
) -> Optional[Dict[str, str]]:
    if domain:
        norm = normalize_domain(domain)
        cred = subscription_credentials_index.get(norm)
        if cred and (cred.get("email") or cred.get("password")):
            return cred
    if name:
        cred = subscription_name_index.get(name.lower())
        if cred and (cred.get("email") or cred.get("password")):
            return cred
    return None


