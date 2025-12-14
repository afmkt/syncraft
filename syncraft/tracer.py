from __future__ import annotations
from typing import  Any
import time
from syncraft.constraint import Bindable
import sqlite3


class Tracer:
    def __enter__(self) -> Tracer:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        pass
    def __init__(self, url: None | str = None) -> None:
        self.log: list[Any] = []

    def push(self, 
             rule: Any, 
             parent: Any | None,
             state: Bindable) -> int: 
        self.log.append( (time.perf_counter_ns(), 
                          rule, 
                          parent,
                          state.cache_key, 
                          state.str_input(ul=False), 
                          None,
                          None,
                          'push') )
        return len(self.log) - 1
        
    
    def pop(self,
            which: int,
            state: Bindable | None,
            result: Any) -> None:
        self.log.append( (time.perf_counter_ns(), 
                          None,
                          None,
                          state.cache_key if state is not None else None, 
                          state.str_input(ul=False) if state is not None else None, 
                          result, 
                          which,
                          'pop') )
        

