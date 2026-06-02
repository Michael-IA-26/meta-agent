"""Factory — retourne le bon adaptateur selon la config cabinet."""
from __future__ import annotations

from apps.jmpartners.backends.base import ComptaBackend


def get_backend(name: str) -> ComptaBackend:
    """
    Retourne le bon adaptateur selon la config cabinet.
    Utilisé par l'orchestrateur :
        backend = get_backend(os.getenv("COMPTA_BACKEND", "sage"))
    """
    from apps.jmpartners.backends.acd_backend import ACDBackend
    from apps.jmpartners.backends.myunisoft_backend import MyUnisoftBackend
    from apps.jmpartners.backends.pennylane_backend import PennylaneBackend
    from apps.jmpartners.backends.sage_backend import SageBackend

    backends: dict[str, type[ComptaBackend]] = {
        "sage": SageBackend,
        "pennylane": PennylaneBackend,
        "myunisoft": MyUnisoftBackend,
        "acd": ACDBackend,
    }
    if name not in backends:
        raise ValueError(f"Backend inconnu : {name!r}. Valeurs : {list(backends)}")
    return backends[name]()
