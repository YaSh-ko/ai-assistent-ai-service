import ssl
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Standard locations for CA certificates on Linux
CA_PATHS = [
    "/etc/ssl/certs/ca-certificates.crt",                  # Debian/Ubuntu/Gentoo etc.
    "/etc/pki/tls/certs/ca-bundle.crt",                    # Fedora/RHEL 6
    "/etc/ssl/ca-bundle.pem",                              # OpenSUSE
    "/etc/pki/tls/cacert.pem",                             # OpenELEC
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",   # CentOS/RHEL 7
]

def get_ca_bundle_path() -> Optional[str]:
    """Find the first existing CA bundle path."""
    for path in CA_PATHS:
        if os.path.exists(path):
            return path
    return None

def get_gigachat_ssl_context() -> ssl.SSLContext:
    """
    Creates a standard SSL context for GigaChat calls.
    Prioritizes system trust store where Russian CA certificates are installed.
    """
    context = ssl.create_default_context()

    ca_bundle = get_ca_bundle_path()
    if ca_bundle:
        try:
            context.load_verify_locations(ca_bundle)
            logger.debug(f"Loaded CA bundle from {ca_bundle}")
        except Exception as e:
            logger.warning(f"Failed to load CA bundle from {ca_bundle}: {e}")

    # Emergency bypass via env var
    if os.getenv("GIGACHAT_VERIFY_SSL", "true").lower() == "false":
        logger.warning("GIGACHAT_VERIFY_SSL is set to FALSE. SSL verification is DISABLED!")
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    return context
