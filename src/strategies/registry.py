import importlib
import inspect
import os
from typing import Dict, List, Optional, Type

from src.strategies.base import Strategy


class StrategyRegistry:
    """Central registry for all strategy classes."""

    def __init__(self):
        self._strategies: Dict[str, Type[Strategy]] = {}

    def register(self, name: str, strategy_class: Type[Strategy]):
        """Register a strategy class by name."""
        if not (inspect.isclass(strategy_class) and issubclass(strategy_class, Strategy)):
            raise TypeError(f"{strategy_class} is not a subclass of Strategy")
        self._strategies[name] = strategy_class

    def get(self, name: str) -> Optional[Type[Strategy]]:
        """Get a strategy class by name."""
        return self._strategies.get(name)

    def list_all(self) -> List[str]:
        """List all registered strategy names."""
        return list(self._strategies.keys())

    def list_by_family(self, family: str) -> List[str]:
        """List strategy names that belong to a given family."""
        results = []
        for name, cls in self._strategies.items():
            defaults = cls.__default_family__ if hasattr(cls, "__default_family__") else None
            if defaults == family:
                results.append(name)
        return results

    def auto_discover(self, package_dir: str = None):
        """Auto-discover and register strategies from the src/strategies directory."""
        if package_dir is None:
            package_dir = os.path.dirname(os.path.abspath(__file__))

        for filename in sorted(os.listdir(package_dir)):
            if filename.startswith("_") or not filename.endswith(".py"):
                continue
            if filename in ("base.py", "registry.py"):
                continue

            module_name = filename[:-3]
            module_path = f"src.strategies.{module_name}"

            try:
                module = importlib.import_module(module_path)
            except Exception as e:
                print(f"Warning: could not import {module_path}: {e}")
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, Strategy)
                    and attr is not Strategy
                    and not inspect.isabstract(attr)
                ):
                    reg_name = getattr(attr, "__strategy_name__", module_name)
                    self._strategies[reg_name] = attr


# Global registry instance
global_registry = StrategyRegistry()
