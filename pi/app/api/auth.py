"""Centralized authentication for FastAPI."""

from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

PLACEHOLDER_TOKENS = {"your-secret-token-here", "CHANGE_ME"}

security = HTTPBearer(auto_error=False)


def get_auth_token(config: dict) -> Optional[str]:
  """Read auth token from config. Returns None if missing, empty, or placeholder."""
  token = config.get("auth", {}).get("token")
  if not token or token in PLACEHOLDER_TOKENS:
    return None
  return token


def create_auth_dependency(config: dict) -> Callable:
  """Factory that returns a FastAPI dependency enforcing bearer token auth.

  Fail-closed: if no token is configured, all protected requests are rejected.
  """
  configured_token = get_auth_token(config)

  async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
  ):
    # No token configured = open access (LAN-only device)
    if configured_token is None:
      return

    if credentials is None or credentials.credentials != configured_token:
      raise HTTPException(
        status_code=401,
        detail="Invalid or missing authentication token",
      )

  return require_auth
