from __future__ import annotations

from fastapi import Response

from .settings import DeliveryProfile


CONTENT_SECURITY_POLICY = (
    "default-src 'self'; base-uri 'none'; connect-src 'self'; "
    "font-src 'self'; form-action 'none'; frame-ancestors 'none'; "
    "img-src 'self' data:; manifest-src 'none'; object-src 'none'; "
    "script-src 'self'; style-src 'self'; worker-src 'none'"
)

_SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=(), payment=(), usb=()",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
}


def apply_public_response_headers(
    response: Response,
    *,
    path: str,
    profile: DeliveryProfile,
) -> None:
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value

    if profile is DeliveryProfile.HOSTED:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    if path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "no-store"
