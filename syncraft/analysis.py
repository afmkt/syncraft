from __future__ import annotations
from typing import Any, Tuple
from dataclasses import dataclass, field, replace
from syncraft.syntax import Syntax, SyntaxSpec, Graph
from syncraft.utils import FrozenDict
@dataclass(frozen=True, slots=True)
class Analyzer:
    graph: Graph
    metadata: FrozenDict[str, Any] = field(default_factory=FrozenDict)
    

    def with_metadata(self, **new_metadata: Any) -> Analyzer:
        updated_metadata = {**self.metadata, **new_metadata}
        return replace(self, metadata=FrozenDict(updated_metadata))


    def __getitem__(self, key: str) -> Any:
        return self.metadata[key]

    def __contains__(self, key: str) -> bool:
        return key in self.metadata
