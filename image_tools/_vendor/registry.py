# Vendored from BasicSR (https://github.com/XPixelGroup/BasicSR)
# Apache License 2.0 — only the Registry class is included (ARCH_REGISTRY used as a
# class decorator; the decorator is a no-op for inference but required so the arch
# files load without modification).

class Registry:
    """Minimal name -> object registry.  Used as a class decorator."""

    def __init__(self, name):
        self._name = name
        self._obj_map = {}

    def _do_register(self, name, obj):
        self._obj_map[name] = obj

    def register(self, obj=None):
        """Can be used as a decorator (@ARCH_REGISTRY.register()) or a plain call.
        Always returns the decorated class unchanged.
        """
        def deco(func_or_class):
            self._do_register(func_or_class.__name__, func_or_class)
            return func_or_class
        if obj is not None:
            return deco(obj)
        return deco

    def get(self, name):
        ret = self._obj_map.get(name)
        if ret is None:
            raise KeyError(f"No object named '{name}' in '{self._name}' registry.")
        return ret

    def __contains__(self, name):
        return name in self._obj_map

    def __iter__(self):
        return iter(self._obj_map.items())


ARCH_REGISTRY = Registry('arch')
