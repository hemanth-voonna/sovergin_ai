"""Shared dependencies for routers."""
from ..security import get_auth_dependency

auth = get_auth_dependency()