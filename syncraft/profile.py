from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, TypeVar, Generic, Callable, Any, Generator, List, Optional, Tuple, ClassVar, DefaultDict, TYPE_CHECKING
if TYPE_CHECKING:
    from syncraft.cache import Rule
from syncraft.constraint import Bindable
from syncraft.ast import SyncraftError
from rich import print
from syncraft.utils import callable_str, is_lazy, is_orelse
from collections import defaultdict
import copy
import random


@dataclass
class ProfileEntry:
    parent: Rule | None = None
    calls: int = 0
    total_time: float = 0.0
    max_time: float = 0.0
    min_time: float = float('inf')
    successes: int = 0
    failures: int = 0
    is_lazy: bool = False
    is_orelse: bool = False


@dataclass
class Profiler:
    dict: Dict[Rule, Dict[int, ProfileEntry]] = field(default_factory=lambda: defaultdict(dict))

    def log(self, parent: Rule | None, rule: Rule, pos: int, duration: float, success: bool) -> None:
        bucket = self.dict[rule]
        entry = bucket.get(pos)
        if entry is None:
            entry = ProfileEntry(parent=parent, is_lazy=is_lazy(rule), is_orelse=is_orelse(rule))
            bucket[pos] = entry
        entry.calls += 1
        entry.total_time += duration
        entry.max_time = max(entry.max_time, duration)
        entry.min_time = min(entry.min_time, duration)
        if success:
            entry.successes += 1
        else:
            entry.failures += 1

    def flat(self, keep_rule: bool = False) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for rule, bucket in self.dict.items():
            for pos, entry in bucket.items():
                result.append({
                    'parent': entry.parent if keep_rule else callable_str(entry.parent),
                    'rule': rule if keep_rule else callable_str(rule),
                    'position': pos,
                    'calls': entry.calls,
                    'total_time': entry.total_time,
                    'max_time': entry.max_time,
                    'min_time': entry.min_time,
                    'successes': entry.successes,
                    'failures': entry.failures,
                    'avg_time': entry.total_time / entry.calls if entry.calls > 0 else 0.0,
                    'success_rate': entry.successes / entry.calls if entry.calls > 0 else 0.0,
                    'is_lazy': entry.is_lazy,
                    'is_orelse': entry.is_orelse,
                })
        return result
    
    def agg(self, 
            *, 
            keep_rule: bool = False, 
            **agg_func: Callable[[List[Any]], Any]) -> List[Dict[str, Any]]:
        flat_data = self.flat(keep_rule=keep_rule)
        if not flat_data:
            return []
        all_columns = flat_data[0].keys()
        agg_cols = set(agg_func.keys())
        group_cols = [col for col in all_columns if col not in agg_cols]
        grouped: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
        for row in flat_data:
            key = tuple(row[col] for col in group_cols)
            grouped[key].append(row)
        result: List[Dict[str, Any]] = []            
        for key, rows in grouped.items():
            agg_row: Dict[str, Any] = {}
            for i, col in enumerate(group_cols):
                agg_row[col] = key[i]
            for col in agg_cols:
                func = agg_func[col]
                values = [row[col] for row in rows]
                agg_row[col] = func(values)
            result.append(agg_row)
        return result
    
    def report(self, lines: Optional[int] = None, sort: str = "total_time", filter: Callable[[Dict[str, Any]], bool] = lambda r: callable_str(r['rule']) != 'map_run') -> None:
        agg_functions = {
            'position': lambda values: 'N/A', # Placeholder for non-numeric column
            'calls': sum,
            'total_time': sum,
            'max_time': max,  # Max of all max_times across positions
            'min_time': min,  # Min of all min_times across positions
            'successes': sum,
            'failures': sum,
            'is_lazy': lambda values: any(values),
            'is_orelse': lambda values: any(values),
            'avg_time': lambda values: sum(values) / len(values) if values else 0.0, # Not actually used in the final report calculation
            'success_rate': lambda values: sum(values) / len(values) if values else 0.0 # Not actually used in the final report calculation
        }        
        rule_data = self.agg(keep_rule=True, **agg_functions) # type: ignore
        if not rule_data:
            print("[Profiler] No profiling data collected.")
            return
        total_calls = sum(r['calls'] for r in rule_data)
        total_time = sum(r['total_time'] for r in rule_data)
        total_successes = sum(r['successes'] for r in rule_data)        
        total_failures = sum(r['failures'] for r in rule_data)
        overall_success_rate = (total_successes / total_calls) if total_calls > 0 else 0.0
        # 2. Print Report
        print("--- ⏱️ Parser Profiler Report ---")
        print("\n## Overall Summary")
        print(f"Total Calls:   {total_calls:,}")
        print(f"Total Time:    {total_time:,.4f} seconds")
        print(f"Total Failures: {total_failures:,}")
        print(f"Total Successes: {total_successes:,}")
        print(f"Success Rate:  {overall_success_rate:.2%}")
        width = 190
        print("\n" + "="*width)        
        # Sort by total_time descending
        rule_data.sort(key=lambda x: x[sort], reverse=True)
        HEADER_FMT = "{:<25} | {:<25} | {:>10} | {:>12} | {:>12} | {:>12} | {:>12} | {:>30}"
        print(HEADER_FMT.format("Rule", "Parent", "Calls", "Total Time", "Avg Time", "Max Time", "Success Rate", "Location"))
        print("-" * width)
        for r in rule_data:
            if not filter(r):
                continue
            rule = r['rule']
            rule_name = callable_str(rule)[:24] # Truncate rule name if too long
            parent = callable_str(r['parent'])[:24]
            # Format numbers for printing
            calls_str = f"{r['calls']:,}"
            total_time_str = f"{r['total_time']:,.4f}"
            avg_call_time_str = f"{r['avg_time']:.6f}"
            max_time_str = f"{r['max_time']:.6f}"
            success_rate_str = f"{r['success_rate']:.2%}"
            rule_location = rule.syntax.spec.location if hasattr(rule, 'syntax') and rule.syntax and hasattr(rule.syntax, 'spec') and rule.syntax.spec and hasattr(rule.syntax.spec, 'location') else "N/A"
            rule_location = rule_location or 'N/A'
            
            # Use fixed-width alignment
            print(f"{rule_name:<25} | {parent:<25} | {calls_str:>10} | {total_time_str:>12} | {avg_call_time_str:>12} | {max_time_str:>12} | {success_rate_str:>12} | {rule_location:>30}")
            if lines is not None:
                lines -= 1
                if lines <= 0:
                    break
            
        print("\n" + "="*width + "\n")
