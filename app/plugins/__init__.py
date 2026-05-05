"""Plugin subsystem (interface + registry only — no concrete plugins ship in the MVP)."""

from app.plugins.base import Plugin, PluginContext, PluginManifest
from app.plugins.registry import PluginRegistry, get_registry

__all__ = ["Plugin", "PluginContext", "PluginManifest", "PluginRegistry", "get_registry"]
