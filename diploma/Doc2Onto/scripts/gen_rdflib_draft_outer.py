"""
Одноразовый генератор для core/graph/rdflib_draft_outer.py.
"""
from __future__ import annotations

from pathlib import Path

import rdflib.namespace as rn

SKIP_DOT = frozenset({"BRICK", "SDO"})


def _namespace_names() -> list[str]:
    return [
        n
        for n in rn.__all__
        if n[0].isupper()
        and n
        not in (
            "Namespace",
            "ClosedNamespace",
            "DefinedNamespace",
            "NamespaceManager",
        )
    ]


def _header(names: list[str]) -> str:
    joined = ",\n    ".join(sorted(names))
    return f'''\
"""
Обёртки стандартных неймспейсов rdflib: термины как DraftNode.

Доступ: ``OUTER.XSD.string``, ``OUTER.RDF.type``.
Для очень больших словарей (BRICK, SDO) только индекс: ``OUTER.BRICK["AHU"]``.
"""
from __future__ import annotations

from rdflib.namespace import (
    {joined},
)
from rdflib.namespace import DefinedNamespace
from rdflib.term import URIRef

from core.graph.draft_graph import DraftNode


def _draft_iri(uri: URIRef) -> DraftNode:
    return DraftNode(DraftNode.Type.IRI, uri, None, None)


class DraftBracketNamespace:
    """Термины только через ``[local_name]`` (без ``__getattr__``)."""

    __slots__ = ("_ns",)

    def __init__(self, ns: DefinedNamespace):
        self._ns = ns

    def __getitem__(self, local_name: str) -> DraftNode:
        return _draft_iri(self._ns[local_name])

'''


def main():
    names = _namespace_names()

    parts: list[str] = [_header(names)]

    for name in sorted(names):
        if name in SKIP_DOT:
            continue
        cls = getattr(rn, name)
        ann = getattr(cls, "__annotations__", {}) or {}
        terms = [k for k in ann if not k.startswith("_")]
        parts.append(f"\nclass _Draft{name}:\n")
        parts.append("    def __init__(self):\n")
        for t in terms:
            parts.append(f"        self.{t} = _draft_iri({name}.{t})\n")

    parts.append("\n\nclass RdfLibDraftOuter:\n")
    parts.append(
        '    """Явный контейнер стандартных неймспейсов rdflib '
        '(подсветка OUTER.<NS>.<term>)."""\n'
    )
    parts.append("\n    def __init__(self):\n")

    for name in sorted(names):
        if name in SKIP_DOT:
            parts.append(f"        self.{name} = DraftBracketNamespace({name})\n")
        else:
            parts.append(f"        self.{name} = _Draft{name}()\n")

    parts.append("\n\nOUTER = RdfLibDraftOuter()\n")

    root = Path(__file__).resolve().parents[1]
    path = root / "core" / "graph" / "rdflib_draft_outer.py"
    path.write_text("".join(parts), encoding="utf-8")
    print("wrote", path, "size", path.stat().st_size)


if __name__ == "__main__":
    main()
