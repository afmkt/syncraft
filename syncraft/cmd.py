import subprocess
import tempfile
from typing import List, Tuple
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Sqlite3Result:
    stdout: Tuple[str, ...] = field(default_factory=tuple)
    stderr: Tuple[str, ...] = field(default_factory=tuple)
    schema: Tuple[str, ...] = field(default_factory=tuple)


class SQLite3:
    def __init__(self, cmd: str = 'sqlite3'):
        self.cmd = cmd

    
    def exec(self, sql: str)->Sqlite3Result:
        with tempfile.NamedTemporaryFile(suffix=".db") as temp_db:
            process = subprocess.run(
                [self.cmd, temp_db.name],
                input=sql.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout = process.stdout.decode('utf-8').strip().splitlines()
            stderr = process.stderr.decode('utf-8').strip().splitlines()
            schema_process = subprocess.run(
                [self.cmd, temp_db.name, '.schema'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            schema = schema_process.stdout.decode('utf-8').strip().splitlines()
            return Sqlite3Result(
                stdout=tuple(stdout),
                stderr=tuple(stderr),
                schema=tuple(schema)
            )
    

if __name__ == "__main__":
    sql = """
    DROP TABLE IF EXISTS test;
    DROP TABLE IF EXISTS error;
    DROP INDEX IF EXISTS idx_name;
    CREATE TABLE d.x (id INTEGER PRIMARY KEY, name TEXT);

    CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT);
    CREATE TABLE IF NOT EXISTS error (id INTEGER PRIMARY KEY, name TEXT); 
    CREATE INDEX IF NOT EXISTS idx_name ON test(name);
    CREATE TRIGGER IF NOT EXISTS trg_test 
    AFTER INSERT ON test 
    BEGIN 
        INSERT INTO error (name) VALUES ('Trigger Error'); 
    END;
    """
    result = SQLite3().exec(sql)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    print("SCHEMA:", result.schema)

