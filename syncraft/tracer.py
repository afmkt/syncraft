from __future__ import annotations
from typing import  Any
import sqlite3


class Tracer:
    def __init__(self, url: None | str = None) -> None:
        self.value_cache: dict[int, str] = {}
        url = url or ':memory:'
        self.conn = sqlite3.connect(url)
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.conn.execute('''
        DROP TABLE IF EXISTS rules
        ''')
        self.conn.execute('''
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER,
            name TEXT,
            location TEXT,
            is_orelse BOOLEAN,
            is_lazy BOOLEAN
        )
        ''')
        self.conn.execute('''
        DROP TABLE IF EXISTS traces
        ''')
        self.conn.execute('''
        CREATE TABLE IF NOT EXISTS traces (
            id INTEGER PRIMARY KEY,
            rule_id INTEGER,
            start_time INTEGER,
            end_time INTEGER,
            start_input TEXT,
            end_input TEXT,
            result TEXT,
            consumed INTEGER,
            FOREIGN KEY (rule_id) REFERENCES rules(id)
        )
        ''')
        self.conn.commit()

    def __enter__(self) -> Tracer:
        self.conn.execute('BEGIN TRANSACTION')
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.conn.execute('COMMIT')

    def save(self, filename: str) -> None:
        self.conn.backup(sqlite3.connect(filename))

    def trace(self, 
            *, 
            rule: Any, 
            parent: Any | None, 
            start_time: int,
            end_time: int,
            start: str,
            end: str | None,
            result: Any,
            consumed: int | None
        ) -> None:
        insert_rule = '''
        INSERT OR IGNORE INTO rules (id, parent_id, name, location, is_orelse, is_lazy) VALUES (?, ?, ?, ?, ?, ?)
        '''
        insert_trace = '''
        INSERT OR IGNORE INTO traces (rule_id, start_time, end_time, start_input, end_input, result, consumed) VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        rule_id = id(rule)
        parent_id = id(parent) if parent is not None else None
        rule_name = str(rule)
        rule_location = rule.location if hasattr(rule, 'location') else 'unknown'
        is_orelse = getattr(rule, 'is_orelse', False)
        is_lazy = getattr(rule, 'is_lazy', False)
        cursor = self.conn.cursor()
        if id(result) in self.value_cache:
            rstr = self.value_cache[id(result)]
        else:
            rstr = str(result)
            self.value_cache[id(result)] = rstr
        cursor.execute(insert_rule, (rule_id, parent_id, rule_name, rule_location, is_orelse, is_lazy))
        cursor.execute(insert_trace, (rule_id, start_time, end_time, start, end, rstr, consumed))
        
