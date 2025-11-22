from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, Callable, Any, List, Optional, Tuple, TYPE_CHECKING, Set
if TYPE_CHECKING:
    from syncraft.cache import Rule
from rich import print
from syncraft.utils import callable_str, is_lazy, is_orelse
from collections import defaultdict


@dataclass
class ProfileEntry:
    rule: Rule
    pos: int
    parent: Rule | None 
    is_lazy: bool 
    is_orelse: bool 

    calls: int = 0
    cumtime: float = 0.0
    max_time: float = 0.0
    min_time: float = float('inf')
    successes: int = 0
    failures: int = 0
    consumption: Dict[int, int] = field(default_factory=dict)
    def log(self, duration: float, success: bool, consumed: int) -> None:
        self.calls += 1
        self.cumtime += duration
        self.max_time = max(self.max_time, duration)
        self.min_time = min(self.min_time, duration)
        if success:
            self.successes += 1
            self.consumption[consumed] = self.consumption.get(consumed, 0) + 1
        else:
            self.failures += 1


    @property
    def avg_cumtime(self) -> float:
        return self.cumtime / self.calls if self.calls > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        return self.successes / self.calls if self.calls > 0 else 0.0

    @property
    def null(self) -> int:
        return self.consumption.get(0, 0)
    
    @property
    def max_consumption(self) -> int:
        return max(self.consumption.keys()) if self.consumption else 0
    
    @property
    def avg_consumption(self) -> float:
        return sum([k * v for k, v in self.consumption.items()]) / sum(self.consumption.values())


    def record(self, keep_rule: bool) -> Dict[str, Any]:
        
        return {
                'rule': self.rule if keep_rule else callable_str(self.rule),
                'parent': self.parent if keep_rule else callable_str(self.parent),
                'position': self.pos,
                'calls': self.calls,
                'cumtime': self.cumtime,
                'max_time': self.max_time,
                'min_time': self.min_time,
                'successes': self.successes,
                'failures': self.failures,
                'avg_cumtime': self.avg_cumtime,
                'success_rate': self.success_rate,
                'null': self.null,
                'max_consumption': self.max_consumption,
                'avg_consumption': self.avg_consumption,
                'is_lazy': self.is_lazy,
                'is_orelse': self.is_orelse,
            }


class Profile:

    @staticmethod
    def deficiency(failures: int, successes: int, cumtime: float) -> float:
        return (failures + 1) * (cumtime) / (successes + 1)

    def __init__(self, sample_interval: int)->None:
        self.sample_interval = sample_interval
        self.dict: Dict[Rule, Tuple[Dict[int, ProfileEntry], int]] = dict()

    
    def should_log(self, rule: Rule) -> Dict[int, ProfileEntry] | None:
        record: Tuple[Dict[int, ProfileEntry], int] | None = self.dict.get(rule)
        if record is None:
            record = (dict(), 0)
        bucket, counter = record
        if counter % self.sample_interval == 0:
            self.dict[rule] = (bucket, 0)
            return bucket
        else:
            self.dict[rule] = (bucket, counter + 1)
            return None


    def log(self, 
            *, 
            record: Dict[int, ProfileEntry], 
            rule: Rule, 
            parent: Rule | None, 
            pos: int, 
            duration: float, 
            success: bool, 
            consumed: int) -> None:
        entry = record.get(pos)
        if entry is None:
            entry = ProfileEntry(rule = rule, pos = pos, parent=parent, is_lazy=is_lazy(rule), is_orelse=is_orelse(rule))
            record[pos] = entry
        entry.log(duration=duration, success=success, consumed=consumed)

    def flat(self, keep_rule: bool = False) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for bucket, _ in self.dict.values():
            for entry in bucket.values():
                result.append(entry.record(keep_rule=keep_rule))
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
    


    def report(self, lines: Optional[int] = None, sort: str = "cumtime", filter: Callable[[Dict[str, Any]], bool] = lambda r: callable_str(r['rule']) != 'map_run') -> None:
        agg_functions = {
            'position': lambda values: values, # Placeholder for non-numeric column
            'calls': sum,
            'cumtime': sum,
            'max_time': max,  # Max of all max_times across positions
            'min_time': min,  # Min of all min_times across positions
            'successes': sum,
            'failures': sum,
            'is_lazy': lambda values: any(values),
            'is_orelse': lambda values: any(values),
            'avg_cumtime': lambda values: sum(values) / len(values) if values else 0.0, # Not actually used in the final report calculation
            'success_rate': lambda values: sum(values) / len(values) if values else 0.0, # Not actually used in the final report calculation
            'null': sum,
            'max_consumption': max,
            'avg_consumption': lambda values: sum(values) / len(values) if values else 0.0,
        }        
        rule_data = self.agg(keep_rule=True, **agg_functions) # type: ignore
        if not rule_data:
            print("[Profiler] No profiling data collected.")
            return
        total_calls = sum(r['calls'] for r in rule_data)
        cumtime = sum(r['cumtime'] for r in rule_data)
        total_successes = sum(r['successes'] for r in rule_data)        
        total_failures = sum(r['failures'] for r in rule_data)
        overall_success_rate = (total_successes / total_calls) if total_calls > 0 else 0.0
        # 2. Print Report
        print("--- ⏱️ Parser Profiler Report ---")
        print("\n## Overall Summary")
        print(f"Total Calls:   {total_calls:,}")
        print(f"Total Time:    {cumtime:,.4f} seconds")
        print(f"Total Failures: {total_failures:,}")
        print(f"Total Successes: {total_successes:,}")
        print(f"Success Rate:  {overall_success_rate:.2%}")
        width = 190
        print("\n" + "="*width)        
        # Sort by cumtime descending
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
            total_time_str = f"{r['cumtime']:,.4f}"
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
