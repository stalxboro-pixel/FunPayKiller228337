"""In-memory registry of loaded plugins. The MVP has zero plugins by default."""

from __future__ import annotations

from threading import RLock

from app.plugins.base import Plugin


class PluginRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        slug = plugin.manifest.slug
        with self._lock:
            if slug in self._plugins:
                raise ValueError(f"Plugin '{slug}' is already registered")
            self._plugins[slug] = plugin

    def unregister(self, slug: str) -> None:
        with self._lock:
            self._plugins.pop(slug, None)

    def all(self) -> list[Plugin]:
        with self._lock:
            return list(self._plugins.values())

    def get(self, slug: str) -> Plugin | None:
        with self._lock:
            return self._plugins.get(slug)


_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry
