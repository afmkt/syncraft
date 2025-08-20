"""
A collection of parsers for SQL grammar using the syncraft library.
https://www.sqlite.org/syntaxdiagrams.html
"""
from __future__ import annotations
from typing import Any
from syncraft.syntax import Syntax, lazy, choice
import syncraft.parser as dsl
from syncraft.diagnostic import rich_error, rich_debug, rich_parser
from sqlglot import TokenType





L_PAREN = dsl.lift(TokenType.L_PAREN)
R_PAREN = dsl.lift(TokenType.R_PAREN)
L_BRACKET = dsl.lift(TokenType.L_BRACKET)
R_BRACKET = dsl.lift(TokenType.R_BRACKET)
L_BRACE = dsl.lift(TokenType.L_BRACE)
R_BRACE = dsl.lift(TokenType.R_BRACE)
COMMA = dsl.lift(TokenType.COMMA)
DOT = dsl.lift(TokenType.DOT)
DASH = dsl.lift(TokenType.DASH)
PLUS = dsl.lift(TokenType.PLUS)
COLON = dsl.lift(TokenType.COLON)
DOTCOLON = dsl.lift(TokenType.DOTCOLON)
DCOLON = dsl.lift(TokenType.DCOLON)
DQMARK = dsl.lift(TokenType.DQMARK)
SEMICOLON = dsl.lift(TokenType.SEMICOLON)
STAR = dsl.lift(TokenType.STAR)
BACKSLASH = dsl.lift(TokenType.BACKSLASH)
SLASH = dsl.lift(TokenType.SLASH)
LT = dsl.lift(TokenType.LT)
LTE = dsl.lift(TokenType.LTE)
GT = dsl.lift(TokenType.GT)
GTE = dsl.lift(TokenType.GTE)
NOT = dsl.lift(TokenType.NOT)
EQ = dsl.lift(TokenType.EQ)
NEQ = dsl.lift(TokenType.NEQ)
NULLSAFE_EQ = dsl.lift(TokenType.NULLSAFE_EQ)
COLON_EQ = dsl.lift(TokenType.COLON_EQ)
AND = dsl.lift(TokenType.AND)
OR = dsl.lift(TokenType.OR)
AMP = dsl.lift(TokenType.AMP)
DPIPE = dsl.lift(TokenType.DPIPE)
PIPE_GT = dsl.lift(TokenType.PIPE_GT)
PIPE = dsl.lift(TokenType.PIPE)
PIPE_SLASH = dsl.lift(TokenType.PIPE_SLASH)
DPIPE_SLASH = dsl.lift(TokenType.DPIPE_SLASH)
CARET = dsl.lift(TokenType.CARET)
CARET_AT = dsl.lift(TokenType.CARET_AT)
TILDA = dsl.lift(TokenType.TILDA)
ARROW = dsl.lift(TokenType.ARROW)
DARROW = dsl.lift(TokenType.DARROW)
FARROW = dsl.lift(TokenType.FARROW)
HASH = dsl.lift(TokenType.HASH)
HASH_ARROW = dsl.lift(TokenType.HASH_ARROW)
DHASH_ARROW = dsl.lift(TokenType.DHASH_ARROW)
LR_ARROW = dsl.lift(TokenType.LR_ARROW)
DAT = dsl.lift(TokenType.DAT)
LT_AT = dsl.lift(TokenType.LT_AT)
AT_GT = dsl.lift(TokenType.AT_GT)
DOLLAR = dsl.lift(TokenType.DOLLAR)
PARAMETER = dsl.lift(TokenType.PARAMETER)
SESSION_PARAMETER = dsl.lift(TokenType.SESSION_PARAMETER)
DAMP = dsl.lift(TokenType.DAMP)
XOR = dsl.lift(TokenType.XOR)
DSTAR = dsl.lift(TokenType.DSTAR)
URI_START = dsl.lift(TokenType.URI_START)
BLOCK_START = dsl.lift(TokenType.BLOCK_START)
BLOCK_END = dsl.lift(TokenType.BLOCK_END)
SPACE = dsl.lift(TokenType.SPACE)
BREAK = dsl.lift(TokenType.BREAK)
STRING = dsl.lift(TokenType.STRING)
NUMBER = dsl.lift(TokenType.NUMBER)
IDENTIFIER = dsl.lift(TokenType.IDENTIFIER)
DATABASE = dsl.lift(TokenType.DATABASE)
COLUMN = dsl.lift(TokenType.COLUMN)
COLUMN_DEF = dsl.lift(TokenType.COLUMN_DEF)
SCHEMA = dsl.lift(TokenType.SCHEMA)
TABLE = dsl.lift(TokenType.TABLE)
WAREHOUSE = dsl.lift(TokenType.WAREHOUSE)
STAGE = dsl.lift(TokenType.STAGE)
STREAMLIT = dsl.lift(TokenType.STREAMLIT)
VAR = dsl.lift(TokenType.VAR)
BIT_STRING = dsl.lift(TokenType.BIT_STRING)
HEX_STRING = dsl.lift(TokenType.HEX_STRING)
BYTE_STRING = dsl.lift(TokenType.BYTE_STRING)
NATIONAL_STRING = dsl.lift(TokenType.NATIONAL_STRING)
RAW_STRING = dsl.lift(TokenType.RAW_STRING)
HEREDOC_STRING = dsl.lift(TokenType.HEREDOC_STRING)
UNICODE_STRING = dsl.lift(TokenType.UNICODE_STRING)
BIT = dsl.lift(TokenType.BIT)
BOOLEAN = dsl.lift(TokenType.BOOLEAN)
TINYINT = dsl.lift(TokenType.TINYINT)
UTINYINT = dsl.lift(TokenType.UTINYINT)
SMALLINT = dsl.lift(TokenType.SMALLINT)
USMALLINT = dsl.lift(TokenType.USMALLINT)
MEDIUMINT = dsl.lift(TokenType.MEDIUMINT)
UMEDIUMINT = dsl.lift(TokenType.UMEDIUMINT)
INT = dsl.lift(TokenType.INT)
UINT = dsl.lift(TokenType.UINT)
BIGINT = dsl.lift(TokenType.BIGINT)
UBIGINT = dsl.lift(TokenType.UBIGINT)
INT128 = dsl.lift(TokenType.INT128)
UINT128 = dsl.lift(TokenType.UINT128)
INT256 = dsl.lift(TokenType.INT256)
UINT256 = dsl.lift(TokenType.UINT256)
FLOAT = dsl.lift(TokenType.FLOAT)
DOUBLE = dsl.lift(TokenType.DOUBLE)
UDOUBLE = dsl.lift(TokenType.UDOUBLE)
DECIMAL = dsl.lift(TokenType.DECIMAL)
DECIMAL32 = dsl.lift(TokenType.DECIMAL32)
DECIMAL64 = dsl.lift(TokenType.DECIMAL64)
DECIMAL128 = dsl.lift(TokenType.DECIMAL128)
DECIMAL256 = dsl.lift(TokenType.DECIMAL256)
UDECIMAL = dsl.lift(TokenType.UDECIMAL)
BIGDECIMAL = dsl.lift(TokenType.BIGDECIMAL)
CHAR = dsl.lift(TokenType.CHAR)
NCHAR = dsl.lift(TokenType.NCHAR)
VARCHAR = dsl.lift(TokenType.VARCHAR)
NVARCHAR = dsl.lift(TokenType.NVARCHAR)
BPCHAR = dsl.lift(TokenType.BPCHAR)
TEXT = dsl.lift(TokenType.TEXT)
MEDIUMTEXT = dsl.lift(TokenType.MEDIUMTEXT)
LONGTEXT = dsl.lift(TokenType.LONGTEXT)
BLOB = dsl.lift(TokenType.BLOB)
MEDIUMBLOB = dsl.lift(TokenType.MEDIUMBLOB)
LONGBLOB = dsl.lift(TokenType.LONGBLOB)
TINYBLOB = dsl.lift(TokenType.TINYBLOB)
TINYTEXT = dsl.lift(TokenType.TINYTEXT)
NAME = dsl.lift(TokenType.NAME)
BINARY = dsl.lift(TokenType.BINARY)
VARBINARY = dsl.lift(TokenType.VARBINARY)
JSON = dsl.lift(TokenType.JSON)
JSONB = dsl.lift(TokenType.JSONB)
TIME = dsl.lift(TokenType.TIME)
TIMETZ = dsl.lift(TokenType.TIMETZ)
TIMESTAMP = dsl.lift(TokenType.TIMESTAMP)
TIMESTAMPTZ = dsl.lift(TokenType.TIMESTAMPTZ)
TIMESTAMPLTZ = dsl.lift(TokenType.TIMESTAMPLTZ)
TIMESTAMPNTZ = dsl.lift(TokenType.TIMESTAMPNTZ)
TIMESTAMP_S = dsl.lift(TokenType.TIMESTAMP_S)
TIMESTAMP_MS = dsl.lift(TokenType.TIMESTAMP_MS)
TIMESTAMP_NS = dsl.lift(TokenType.TIMESTAMP_NS)
DATETIME = dsl.lift(TokenType.DATETIME)
DATETIME2 = dsl.lift(TokenType.DATETIME2)
DATETIME64 = dsl.lift(TokenType.DATETIME64)
SMALLDATETIME = dsl.lift(TokenType.SMALLDATETIME)
DATE = dsl.lift(TokenType.DATE)
DATE32 = dsl.lift(TokenType.DATE32)
INT4RANGE = dsl.lift(TokenType.INT4RANGE)
INT4MULTIRANGE = dsl.lift(TokenType.INT4MULTIRANGE)
INT8RANGE = dsl.lift(TokenType.INT8RANGE)
INT8MULTIRANGE = dsl.lift(TokenType.INT8MULTIRANGE)
NUMRANGE = dsl.lift(TokenType.NUMRANGE)
NUMMULTIRANGE = dsl.lift(TokenType.NUMMULTIRANGE)
TSRANGE = dsl.lift(TokenType.TSRANGE)
TSMULTIRANGE = dsl.lift(TokenType.TSMULTIRANGE)
TSTZRANGE = dsl.lift(TokenType.TSTZRANGE)
TSTZMULTIRANGE = dsl.lift(TokenType.TSTZMULTIRANGE)
DATERANGE = dsl.lift(TokenType.DATERANGE)
DATEMULTIRANGE = dsl.lift(TokenType.DATEMULTIRANGE)
UUID = dsl.lift(TokenType.UUID)
GEOGRAPHY = dsl.lift(TokenType.GEOGRAPHY)
NULLABLE = dsl.lift(TokenType.NULLABLE)
GEOMETRY = dsl.lift(TokenType.GEOMETRY)
POINT = dsl.lift(TokenType.POINT)
RING = dsl.lift(TokenType.RING)
LINESTRING = dsl.lift(TokenType.LINESTRING)
MULTILINESTRING = dsl.lift(TokenType.MULTILINESTRING)
POLYGON = dsl.lift(TokenType.POLYGON)
MULTIPOLYGON = dsl.lift(TokenType.MULTIPOLYGON)
HLLSKETCH = dsl.lift(TokenType.HLLSKETCH)
HSTORE = dsl.lift(TokenType.HSTORE)
SUPER = dsl.lift(TokenType.SUPER)
SERIAL = dsl.lift(TokenType.SERIAL)
SMALLSERIAL = dsl.lift(TokenType.SMALLSERIAL)
BIGSERIAL = dsl.lift(TokenType.BIGSERIAL)
XML = dsl.lift(TokenType.XML)
YEAR = dsl.lift(TokenType.YEAR)
USERDEFINED = dsl.lift(TokenType.USERDEFINED)
MONEY = dsl.lift(TokenType.MONEY)
SMALLMONEY = dsl.lift(TokenType.SMALLMONEY)
ROWVERSION = dsl.lift(TokenType.ROWVERSION)
IMAGE = dsl.lift(TokenType.IMAGE)
VARIANT = dsl.lift(TokenType.VARIANT)
OBJECT = dsl.lift(TokenType.OBJECT)
INET = dsl.lift(TokenType.INET)
IPADDRESS = dsl.lift(TokenType.IPADDRESS)
IPPREFIX = dsl.lift(TokenType.IPPREFIX)
IPV4 = dsl.lift(TokenType.IPV4)
IPV6 = dsl.lift(TokenType.IPV6)
ENUM = dsl.lift(TokenType.ENUM)
ENUM8 = dsl.lift(TokenType.ENUM8)
ENUM16 = dsl.lift(TokenType.ENUM16)
FIXEDSTRING = dsl.lift(TokenType.FIXEDSTRING)
LOWCARDINALITY = dsl.lift(TokenType.LOWCARDINALITY)
NESTED = dsl.lift(TokenType.NESTED)
AGGREGATEFUNCTION = dsl.lift(TokenType.AGGREGATEFUNCTION)
SIMPLEAGGREGATEFUNCTION = dsl.lift(TokenType.SIMPLEAGGREGATEFUNCTION)
TDIGEST = dsl.lift(TokenType.TDIGEST)
UNKNOWN = dsl.lift(TokenType.UNKNOWN)
VECTOR = dsl.lift(TokenType.VECTOR)
DYNAMIC = dsl.lift(TokenType.DYNAMIC)
VOID = dsl.lift(TokenType.VOID)
ALIAS = dsl.lift(TokenType.ALIAS)
ALTER = dsl.lift(TokenType.ALTER)
ALWAYS = dsl.lift(TokenType.ALWAYS)
ALL = dsl.lift(TokenType.ALL)
ANTI = dsl.lift(TokenType.ANTI)
ANY = dsl.lift(TokenType.ANY)
APPLY = dsl.lift(TokenType.APPLY)
ARRAY = dsl.lift(TokenType.ARRAY)
ASC = dsl.lift(TokenType.ASC)
ASOF = dsl.lift(TokenType.ASOF)
ATTACH = dsl.lift(TokenType.ATTACH)
AUTO_INCREMENT = dsl.lift(TokenType.AUTO_INCREMENT)
BEGIN = dsl.lift(TokenType.BEGIN)
BETWEEN = dsl.lift(TokenType.BETWEEN)
BULK_COLLECT_INTO = dsl.lift(TokenType.BULK_COLLECT_INTO)
CACHE = dsl.lift(TokenType.CACHE)
CASE = dsl.lift(TokenType.CASE)
CHARACTER_SET = dsl.lift(TokenType.CHARACTER_SET)
CLUSTER_BY = dsl.lift(TokenType.CLUSTER_BY)
COLLATE = dsl.lift(TokenType.COLLATE)
COMMAND = dsl.lift(TokenType.COMMAND)
COMMENT = dsl.lift(TokenType.COMMENT)
COMMIT = dsl.lift(TokenType.COMMIT)
CONNECT_BY = dsl.lift(TokenType.CONNECT_BY)
CONSTRAINT = dsl.lift(TokenType.CONSTRAINT)
COPY = dsl.lift(TokenType.COPY)
CREATE = dsl.lift(TokenType.CREATE)
CROSS = dsl.lift(TokenType.CROSS)
CUBE = dsl.lift(TokenType.CUBE)
CURRENT_DATE = dsl.lift(TokenType.CURRENT_DATE)
CURRENT_DATETIME = dsl.lift(TokenType.CURRENT_DATETIME)
CURRENT_SCHEMA = dsl.lift(TokenType.CURRENT_SCHEMA)
CURRENT_TIME = dsl.lift(TokenType.CURRENT_TIME)
CURRENT_TIMESTAMP = dsl.lift(TokenType.CURRENT_TIMESTAMP)
CURRENT_USER = dsl.lift(TokenType.CURRENT_USER)
DECLARE = dsl.lift(TokenType.DECLARE)
DEFAULT = dsl.lift(TokenType.DEFAULT)
DELETE = dsl.lift(TokenType.DELETE)
DESC = dsl.lift(TokenType.DESC)
DESCRIBE = dsl.lift(TokenType.DESCRIBE)
DETACH = dsl.lift(TokenType.DETACH)
DICTIONARY = dsl.lift(TokenType.DICTIONARY)
DISTINCT = dsl.lift(TokenType.DISTINCT)
DISTRIBUTE_BY = dsl.lift(TokenType.DISTRIBUTE_BY)
DIV = dsl.lift(TokenType.DIV)
DROP = dsl.lift(TokenType.DROP)
ELSE = dsl.lift(TokenType.ELSE)
END = dsl.lift(TokenType.END)
ESCAPE = dsl.lift(TokenType.ESCAPE)
EXCEPT = dsl.lift(TokenType.EXCEPT)
EXECUTE = dsl.lift(TokenType.EXECUTE)
EXISTS = dsl.lift(TokenType.EXISTS)
FALSE = dsl.lift(TokenType.FALSE)
FETCH = dsl.lift(TokenType.FETCH)
FILE_FORMAT = dsl.lift(TokenType.FILE_FORMAT)
FILTER = dsl.lift(TokenType.FILTER)
FINAL = dsl.lift(TokenType.FINAL)
FIRST = dsl.lift(TokenType.FIRST)
FOR = dsl.lift(TokenType.FOR)
FORCE = dsl.lift(TokenType.FORCE)
FOREIGN_KEY = dsl.lift(TokenType.FOREIGN_KEY)
FORMAT = dsl.lift(TokenType.FORMAT)
FROM = dsl.lift(TokenType.FROM)
FULL = dsl.lift(TokenType.FULL)
FUNCTION = dsl.lift(TokenType.FUNCTION)
GET = dsl.lift(TokenType.GET)
GLOB = dsl.lift(TokenType.GLOB)
GLOBAL = dsl.lift(TokenType.GLOBAL)
GRANT = dsl.lift(TokenType.GRANT)
GROUP_BY = dsl.lift(TokenType.GROUP_BY)
GROUPING_SETS = dsl.lift(TokenType.GROUPING_SETS)
HAVING = dsl.lift(TokenType.HAVING)
HINT = dsl.lift(TokenType.HINT)
IGNORE = dsl.lift(TokenType.IGNORE)
ILIKE = dsl.lift(TokenType.ILIKE)

IN = dsl.lift(TokenType.IN)
INDEX = dsl.lift(TokenType.INDEX)
INNER = dsl.lift(TokenType.INNER)
INSERT = dsl.lift(TokenType.INSERT)
INTERSECT = dsl.lift(TokenType.INTERSECT)
INTERVAL = dsl.lift(TokenType.INTERVAL)
INTO = dsl.lift(TokenType.INTO)
INTRODUCER = dsl.lift(TokenType.INTRODUCER)
IRLIKE = dsl.lift(TokenType.IRLIKE)
IS = dsl.lift(TokenType.IS)
ISNULL = dsl.lift(TokenType.ISNULL)
JOIN = dsl.lift(TokenType.JOIN)
JOIN_MARKER = dsl.lift(TokenType.JOIN_MARKER)
KEEP = dsl.lift(TokenType.KEEP)
KEY = dsl.lift(TokenType.KEY)
KILL = dsl.lift(TokenType.KILL)
LANGUAGE = dsl.lift(TokenType.LANGUAGE)
LATERAL = dsl.lift(TokenType.LATERAL)
LEFT = dsl.lift(TokenType.LEFT)
LIKE = dsl.lift(TokenType.LIKE)

LIMIT = dsl.lift(TokenType.LIMIT)
LIST = dsl.lift(TokenType.LIST)
LOAD = dsl.lift(TokenType.LOAD)
LOCK = dsl.lift(TokenType.LOCK)
MAP = dsl.lift(TokenType.MAP)
MATCH_CONDITION = dsl.lift(TokenType.MATCH_CONDITION)
MATCH_RECOGNIZE = dsl.lift(TokenType.MATCH_RECOGNIZE)
MEMBER_OF = dsl.lift(TokenType.MEMBER_OF)
MERGE = dsl.lift(TokenType.MERGE)
MOD = dsl.lift(TokenType.MOD)
MODEL = dsl.lift(TokenType.MODEL)
NATURAL = dsl.lift(TokenType.NATURAL)
NEXT = dsl.lift(TokenType.NEXT)
NOTHING = dsl.lift(TokenType.NOTHING)
NOTNULL = dsl.lift(TokenType.NOTNULL)
NULL = dsl.lift(TokenType.NULL)
OBJECT_IDENTIFIER = dsl.lift(TokenType.OBJECT_IDENTIFIER)
OFFSET = dsl.lift(TokenType.OFFSET)
ON = dsl.lift(TokenType.ON)
ONLY = dsl.lift(TokenType.ONLY)
OPERATOR = dsl.lift(TokenType.OPERATOR)
ORDER_BY = dsl.lift(TokenType.ORDER_BY)
ORDER_SIBLINGS_BY = dsl.lift(TokenType.ORDER_SIBLINGS_BY)
ORDERED = dsl.lift(TokenType.ORDERED)
ORDINALITY = dsl.lift(TokenType.ORDINALITY)
OUTER = dsl.lift(TokenType.OUTER)
OVER = dsl.lift(TokenType.OVER)
OVERLAPS = dsl.lift(TokenType.OVERLAPS)
OVERWRITE = dsl.lift(TokenType.OVERWRITE)
PARTITION = dsl.lift(TokenType.PARTITION)
PARTITION_BY = dsl.lift(TokenType.PARTITION_BY)
PERCENT = dsl.lift(TokenType.PERCENT)
PIVOT = dsl.lift(TokenType.PIVOT)
PLACEHOLDER = dsl.lift(TokenType.PLACEHOLDER)
POSITIONAL = dsl.lift(TokenType.POSITIONAL)
PRAGMA = dsl.lift(TokenType.PRAGMA)
PREWHERE = dsl.lift(TokenType.PREWHERE)
PRIMARY_KEY = dsl.lift(TokenType.PRIMARY_KEY)
PROCEDURE = dsl.lift(TokenType.PROCEDURE)
PROPERTIES = dsl.lift(TokenType.PROPERTIES)
PSEUDO_TYPE = dsl.lift(TokenType.PSEUDO_TYPE)
PUT = dsl.lift(TokenType.PUT)
QUALIFY = dsl.lift(TokenType.QUALIFY)
QUOTE = dsl.lift(TokenType.QUOTE)
RANGE = dsl.lift(TokenType.RANGE)
RECURSIVE = dsl.lift(TokenType.RECURSIVE)
REFRESH = dsl.lift(TokenType.REFRESH)
RENAME = dsl.lift(TokenType.RENAME)
REPLACE = dsl.lift(TokenType.REPLACE)
RETURNING = dsl.lift(TokenType.RETURNING)
REFERENCES = dsl.lift(TokenType.REFERENCES)
RIGHT = dsl.lift(TokenType.RIGHT)
RLIKE = dsl.lift(TokenType.RLIKE)
ROLLBACK = dsl.lift(TokenType.ROLLBACK)
ROLLUP = dsl.lift(TokenType.ROLLUP)
ROW = dsl.lift(TokenType.ROW)
ROWS = dsl.lift(TokenType.ROWS)
SELECT = dsl.lift(TokenType.SELECT)
SEMI = dsl.lift(TokenType.SEMI)
SEPARATOR = dsl.lift(TokenType.SEPARATOR)
SEQUENCE = dsl.lift(TokenType.SEQUENCE)
SERDE_PROPERTIES = dsl.lift(TokenType.SERDE_PROPERTIES)
SET = dsl.lift(TokenType.SET)
SETTINGS = dsl.lift(TokenType.SETTINGS)
SHOW = dsl.lift(TokenType.SHOW)
SIMILAR_TO = dsl.lift(TokenType.SIMILAR_TO)
SOME = dsl.lift(TokenType.SOME)
SORT_BY = dsl.lift(TokenType.SORT_BY)
START_WITH = dsl.lift(TokenType.START_WITH)
STORAGE_INTEGRATION = dsl.lift(TokenType.STORAGE_INTEGRATION)
STRAIGHT_JOIN = dsl.lift(TokenType.STRAIGHT_JOIN)
STRUCT = dsl.lift(TokenType.STRUCT)
SUMMARIZE = dsl.lift(TokenType.SUMMARIZE)
TABLE_SAMPLE = dsl.lift(TokenType.TABLE_SAMPLE)
TAG = dsl.lift(TokenType.TAG)
TEMPORARY = dsl.lift(TokenType.TEMPORARY)    
TOP = dsl.lift(TokenType.TOP)
THEN = dsl.lift(TokenType.THEN)
TRUE = dsl.lift(TokenType.TRUE)
TRUNCATE = dsl.lift(TokenType.TRUNCATE)
UNCACHE = dsl.lift(TokenType.UNCACHE)
UNION = dsl.lift(TokenType.UNION)
UNNEST = dsl.lift(TokenType.UNNEST)
UNPIVOT = dsl.lift(TokenType.UNPIVOT)
UPDATE = dsl.lift(TokenType.UPDATE)
USE = dsl.lift(TokenType.USE)
USING = dsl.lift(TokenType.USING)
VALUES = dsl.lift(TokenType.VALUES)
VIEW = dsl.lift(TokenType.VIEW)
VOLATILE = dsl.lift(TokenType.VOLATILE)
WHEN = dsl.lift(TokenType.WHEN)
WHERE = dsl.lift(TokenType.WHERE)
WINDOW = dsl.lift(TokenType.WINDOW)
WITH = dsl.lift(TokenType.WITH)
UNIQUE = dsl.lift(TokenType.UNIQUE)
VERSION_SNAPSHOT = dsl.lift(TokenType.VERSION_SNAPSHOT)
TIMESTAMP_SNAPSHOT = dsl.lift(TokenType.TIMESTAMP_SNAPSHOT)
OPTION = dsl.lift(TokenType.OPTION)
SINK = dsl.lift(TokenType.SINK)
SOURCE = dsl.lift(TokenType.SOURCE)
ANALYZE = dsl.lift(TokenType.ANALYZE)
NAMESPACE = dsl.lift(TokenType.NAMESPACE)
EXPORT = dsl.lift(TokenType.EXPORT)
HIVE_TOKEN_STREAM = dsl.lift(TokenType.HIVE_TOKEN_STREAM)

ABORT = dsl.lift("ABORT")
FAIL = dsl.lift("FAIL")
LOOP = dsl.lift("LOOP")
WHILE = dsl.lift("WHILE")
TRIGGER  = dsl.lift("TRIGGER")
TEMP = dsl.lift("TEMP")
IF = dsl.lift("IF")

BEFORE = dsl.lift("BEFORE")
AFTER = dsl.lift("AFTER")
INSTEAD = dsl.lift("INSTEAD")
OF = dsl.lift("OF")
EACH = dsl.lift("EACH")

ADD = dsl.lift("ADD")
TO = dsl.lift("TO")

RAISE = dsl.lift("RAISE")
RETURNS = dsl.lift("RETURNS")
PRIMARY = dsl.lift("PRIMARY")
NULLS = dsl.lift("NULLS")
LAST = dsl.lift("LAST")
CONFLICT = dsl.lift("CONFLICT")
CHECK = dsl.lift("CHECK")
GENERATED = dsl.lift("GENERATED")
STORED = dsl.lift("STORED")
VIRTUAL = dsl.lift("VIRTUAL")
AS = ALIAS
CASCADE = dsl.lift("CASCADE")
RESTRICT = dsl.lift("RESTRICT")
NO = dsl.lift("NO")
ACTION = dsl.lift("ACTION")
NO_ACTION = NO >> ACTION
MATCH = dsl.lift("MATCH")
DEFERRABLE = dsl.lift("DEFERRABLE")
INITIALLY = dsl.lift("INITIALLY")
IMMEDIATE = dsl.lift("IMMEDIATE")
DEFERRED = dsl.lift("DEFERRED")
RELY = dsl.lift("RELY")
NORELY = dsl.lift("NORELY")
VALIDATE = dsl.lift("VALIDATE")
NOVALIDATE = dsl.lift("NOVALIDATE")
EXCLUSIVE = dsl.lift("EXCLUSIVE")
TRANSACTION = dsl.lift("TRANSACTION")
WITHOUT = dsl.lift("WITHOUT")
ROWID = dsl.lift("ROWID")
STRICT = dsl.lift("STRICT")
MATERIALIZED = dsl.lift("MATERIALIZED")
DO = dsl.lift("DO")
RELEASE = dsl.lift("RELEASE")
SAVEPOINT = dsl.lift("SAVEPOINT")
REINDEX = dsl.lift("REINDEX")
INDEXED = dsl.lift("INDEXED")
VACUUM = dsl.lift("VACUUM")
GROUP = dsl.lift("GROUP")
GROUPS = dsl.lift("GROUPS")
UNBOUNDED = dsl.lift("UNBOUNDED")
PRECEDING = dsl.lift("PRECEDING")
FOLLOWING = dsl.lift("FOLLOWING")
CURRENT = dsl.lift("CURRENT")
EXCLUDE = dsl.lift("EXCLUDE")
OTHERS = dsl.lift("OTHERS")
TIES = dsl.lift("TIES")
BY = dsl.lift("BY")
CAST = dsl.lift("CAST")
REGEXP = dsl.lift("REGEXP")

var = dsl.variable()
string = dsl.string()
number = dsl.number()

signed_number = ~(PLUS | DASH) + number
literal_value = (number | string | BLOB | NULL | TRUE | FALSE | CURRENT_DATE | CURRENT_TIME | CURRENT_TIMESTAMP)
if_not_exists = (IF >> NOT >> EXISTS)
if_exists = (IF >> EXISTS)
bind_parameter = ((PLACEHOLDER >> ~number) | (COLON >> var) | (PARAMETER >> var) | var)
schema_name = (var // DOT)
table_name = var
view_name = var
trigger_name = var
constraint_name = var
table_as_alias = (table_name // ~(~AS + var))
column_name = var
index_name = var
table_function_name = var
table_alias = var
alias = var
window_name = var
for_each_row = (FOR >> EACH >> ROW)
unary_operator = (PLUS | DASH)
binary_operator = (PLUS | DASH | STAR | SLASH | EQ | NEQ | GT | GTE | LT | LTE)
compound_operator = ((UNION >> ~ALL) | EXCEPT | INTERSECT)

collate_name = var
function_name = var
expr = lazy(lambda: expression())
frame_spec = ((RANGE | ROWS | GROUPS) >> (
                                                (UNBOUNDED >> PRECEDING)
                                                | (expr >> PRECEDING)
                                                | (CURRENT >> ROW)
                                                | (BETWEEN >> (
                                                    UNBOUNDED >> PRECEDING
                                                    | expr >> PRECEDING
                                                    | CURRENT >> ROW
                                                    | expr >> FOLLOWING
                                                ) >> AND >> (
                                                    expr >> PRECEDING
                                                    | CURRENT >> ROW
                                                    | expr >> FOLLOWING
                                                    | UNBOUNDED >> FOLLOWING
                                                ))
                                            ) >> ~(
                                                EXCLUDE >> ((CURRENT >> ROW) | GROUP | (NO >> OTHERS) | TIES)
                                            ))

join_operator = ((COMMA 
                    | JOIN 
                    | CROSS >> JOIN
                    | NATURAL >> (JOIN
                                    | INNER >> ~OUTER >>JOIN
                                    | LEFT >> ~OUTER >> JOIN
                                    | RIGHT >> ~OUTER >> JOIN
                                    | FULL >> ~OUTER >> JOIN
                                    )))

join_constraint = ~((ON >> expr) | (USING >> var.parens(COMMA, L_PAREN, R_PAREN)))

ordering_term = (expr >> ~(COLLATE >> collate_name) >> ~(ASC | DESC) >> ~(NULLS >> (LAST | FIRST)))
function_argument = (~STAR | (~DISTINCT >> expr.sep_by(COMMA) >> ~(ORDER_BY >> ordering_term.sep_by(COMMA))))
filter_clause = (FILTER >> (WHERE >> expr).between(L_PAREN, R_PAREN))
over_clause = (OVER >> ~(window_name | L_PAREN >> ~var >> (
                                                                            ~(PARTITION >> BY >> expr.sep_by(COMMA))
                                                                            >> ~(ORDER_BY >> ordering_term.sep_by(COMMA))
                                                                            >> ~frame_spec
                                                                        ) // R_PAREN))
                                                                            
typed_name = var >> ~ signed_number.parens(COMMA, L_PAREN, R_PAREN)
returning_clause = RETURNING >> (expr | STAR | (expr >> ~AS >> var)).sep_by(COMMA) 

select_stmt = lazy(lambda: select_statement())

common_table_expression = (table_name >> ~column_name.parens(COMMA, L_PAREN, R_PAREN) >> AS >> ~NOT >> ~MATERIALIZED >> select_stmt.between(L_PAREN, R_PAREN))

indexed_column = (expr | var) >> ~(COLLATE >> var) >> ~(ASC | DESC) 
upsert_clause = (ON >> CONFLICT >> ~(indexed_column.parens(COMMA, L_PAREN, R_PAREN) >> ~(WHERE >> expr))
            >> DO
            >> (
                NOTHING 
                | (UPDATE 
                   >> SET 
                   >> ((column_name 
                        | column_name.parens(COMMA, L_PAREN, R_PAREN)) 
                        >> EQ 
                        >> expr).sep_by(COMMA) 
                >> ~(WHERE >> expr))
            )
            ).many()

window_defn = L_PAREN >> ~window_name >> ~(PARTITION >> BY >> expr.sep_by(COMMA)) >> ~(ORDER_BY >> ordering_term.sep_by(COMMA) >> ~frame_spec) // R_PAREN
result_columns = ((expr >> ~(~AS >> var)) | STAR | (table_name >> DOT>>var))
table_subquery = lazy(lambda: table_or_subquery())
join_clause = (table_subquery >> ~((join_operator >> table_subquery >> join_constraint).many()))
indexed_column = (expr | column_name) >> ~(COLLATE >> collate_name) >> ~(ASC | DESC)
conflict_clause = ON >> CONFLICT >> (ROLLBACK | ABORT | FAIL | IGNORE | REPLACE)
foreign_key_clause = (REFERENCES 
                      >> table_name 
                      >> ~column_name.parens(COMMA, L_PAREN, R_PAREN) 
                      >> ((ON >> (DELETE | UPDATE) >> (
    (SET >> (NULL | DEFAULT)) | CASCADE | RESTRICT | NO_ACTION
)) | (MATCH  >> var)).many() >> ~(~NOT >> DEFERRABLE) >> ~(INITIALLY >> (DEFERRED | IMMEDIATE)))

qualified_table_name = ~schema_name >> table_name >> ~(AS >> alias) >> ~((INDEXED >> BY >> index_name) | (NOT >> INDEXED))

update_stmt = (
        WITH >> ~(RECURSIVE >> common_table_expression.sep_by(COMMA))>>
        UPDATE>>
        ~(OR >> (ABORT | IGNORE | FAIL | REPLACE | ROLLBACK))>>
        qualified_table_name>>
        SET >> (var | var.parens(COMMA, L_PAREN, R_PAREN)) >> EQ >> expr>>
        ~(FROM >> (table_subquery.sep_by(COMMA) | join_clause))>>
        ~(WHERE >> expr)>>
        ~returning_clause>>
        ~SEMICOLON
    )

update_stmt_limited = (
        WITH >> ~(RECURSIVE >> common_table_expression.sep_by(COMMA))>>
        UPDATE>>
        ~(OR >> (ABORT | IGNORE | FAIL | REPLACE | ROLLBACK))>>
        qualified_table_name>>
        SET >> ((column_name | column_name.parens(COMMA, L_PAREN, R_PAREN)) >> EQ >> expr).sep_by(COMMA)>>
        ~(FROM >> (table_subquery.sep_by(COMMA) | join_clause))>>
        ~(WHERE >> expr)>>
        ~returning_clause>>
        ~(ORDER_BY >> ordering_term.sep_by(COMMA))>>
        ~(LIMIT >> expr >> ~((OFFSET >> expr) | (COMMA >> expr)))>>
        ~SEMICOLON
    )


def table_or_subquery()->Syntax[Any, Any]:
    t1 = ~schema_name >> table_as_alias >> ~((INDEXED >> BY >> index_name)|(NOT >> INDEXED))
    t2 = ~schema_name >> table_function_name >> expr.parens(COMMA, L_PAREN, R_PAREN) >> ~(~AS >> var)
    t3 = select_stmt.between(L_PAREN, R_PAREN) >> ~(~AS >> var)
    t4 = table_subquery.parens(COMMA, L_PAREN, R_PAREN)
    t5 = join_clause.between(L_PAREN, R_PAREN) 
    return (t1 | t2 | t3 | t4 | t5).as_(Syntax[Any, Any])


def expression() -> Syntax[Any, Any]:
    return choice(
        literal_value,
        bind_parameter,
        ~(~schema_name >> table_name >> DOT) >> column_name, 
        unary_operator >> expr,
        expr >> binary_operator >> expr,
        function_name 
            >> function_argument.between(L_PAREN, R_PAREN) 
            >> ~filter_clause 
            >> ~over_clause,
        L_PAREN >> expr.sep_by(COMMA) // R_PAREN,
        CAST >> L_PAREN >> expr >> AS >> typed_name >> R_PAREN,
        expr >> COLLATE >> var,
        expr >> ~NOT >> LIKE >> expr >> ~(ESCAPE >> expr),
        expr >> ~NOT >> (GLOB | REGEXP | MATCH) >> expr,
        expr >> (ISNULL | NOTNULL | (NOT >> NULL)),
        expr >> IS >> ~NOT >> ~(DISTINCT >> FROM) >> expr,
        expr >> ~NOT >> BETWEEN >> expr >> (AND >> expr),
        expr >> ~NOT >> IN >> L_PAREN >> (expr.sep_by(COMMA) | select_stmt) // R_PAREN,
        expr >> ~NOT >> IN >> ~schema_name >> (table_name | (function_name >> expr.parens(COMMA, L_PAREN, R_PAREN))),
        ~NOT >> ~EXISTS >> select_stmt.between(L_PAREN, R_PAREN),
        CASE >> ~expr >> (WHEN >> expr >> THEN >> expr).many() >> ~(ELSE >> expr) // END,
    ).as_(Syntax[Any, Any])

def select_statement() -> Syntax[Any, Any]:
    select_clause = SELECT >> ~(DISTINCT | ALL) >> result_columns.sep_by(COMMA)
    from_clause = FROM >> (table_subquery.sep_by(COMMA) | join_clause)
    where_clause = WHERE >> expr
    having_clause = HAVING >> expr
    group_by_clause = GROUP >> BY >> expr.sep_by(COMMA)
    window_clause = WINDOW >> (window_name >> AS >> window_defn).sep_by(COMMA)
    value_clause = VALUES >> expr.parens(COMMA, L_PAREN, R_PAREN).sep_by(COMMA)
    limit_clause = LIMIT >> expr >> ~((OFFSET >> expr) | (COMMA >> expr))
    ordering_clause = ORDER_BY >> ordering_term.sep_by(COMMA)
    select_core = value_clause | (select_clause >> ~from_clause >> ~(where_clause >> ~having_clause) >> ~(group_by_clause >> ~having_clause) >> ~window_clause)
    return (
        WITH >> ~(RECURSIVE >> common_table_expression.sep_by(COMMA))
         >> select_core.sep_by(compound_operator)
         >> ~(ordering_clause >> ~limit_clause)
         >> ~SEMICOLON
    ).as_(Syntax[Any, Any])

column_constraint = ~(CONSTRAINT >> constraint_name) >> (
    (PRIMARY >> KEY >> ~(ASC | DESC) >> ~conflict_clause >> AUTO_INCREMENT)
    | (NOT >> NULL >> conflict_clause)
    | (UNIQUE >> conflict_clause)
    | (CHECK >> expr)
    | (DEFAULT >> (literal_value | signed_number | expr))
    | (COLLATE >> collate_name)
    | ~(GENERATED >> ALWAYS) >> AS >> expr // ~(STORED | VIRTUAL)
)

column_def = (
            var>>
            typed_name>>
            ~column_constraint>>
            ~ SEMICOLON
        )

table_options = ((WITHOUT >> ROWID) | STRICT).sep_by(COMMA)

table_constraint = ~(CONSTRAINT >> constraint_name) >> choice(
    (PRIMARY >> KEY >> ~(ASC | DESC) >> ~conflict_clause >> AUTO_INCREMENT),
    (UNIQUE >> conflict_clause),
    (CHECK >> expr),
    foreign_key_clause
)


rename_table_stmt = (
            ALTER>>
            TABLE>>
            ~schema_name>>
            table_name>>
            RENAME >> TO >> var>>
            ~ SEMICOLON
        )
    

rename_column_stmt = (
             ALTER>>
             TABLE>>
            ~schema_name>>
            table_name>>
             RENAME>>
             COLUMN>>
             column_name>>
             TO>>
            column_name>>
            ~ SEMICOLON
        )

add_column_stmt = (
            ALTER>>
            TABLE>>
            ~schema_name>>
            table_name>>
            ADD>>
            COLUMN>>
            column_name>>
            column_def>>
            ~ SEMICOLON
        )


drop_column_stmt = (
            ALTER>>
            TABLE>>
            ~schema_name>>
            table_name>>
            DROP>>
            COLUMN>>
            column_name>>
            ~ SEMICOLON
        )

alter_table_stmt = rename_table_stmt | rename_column_stmt | add_column_stmt | drop_column_stmt


analyze_stmt = (
            ANALYZE>>
            ~schema_name>>
            table_name>>
            ~SEMICOLON
        )
    

attach_stmt = (
            ATTACH>>
            ~ DATABASE>>
            expr>>
            ~(AS >> var)>>
            ~SEMICOLON
        )

begin_stmt = (
            BEGIN>>
            ~IMMEDIATE>>
            ~DEFERRED>>
            ~EXCLUSIVE>>
            ~TRANSACTION>>
            ~SEMICOLON
        )
    


commit_stmt = (
            (COMMIT | END)>>
            ~TRANSACTION>>
            ~SEMICOLON
        )
    

create_index_stmt = (
            CREATE>>
            ~(TEMPORARY | TEMP)>>
            ~UNIQUE>>
            INDEX>>
            ~if_not_exists>>
            ~schema_name>>
            index_name>>
            ON>>
            table_name>>
            column_name.parens(COMMA, L_PAREN, R_PAREN)>>
            ~(WHERE >> expr)>>
            ~SEMICOLON
        )
    

create_table_stmt = (
            CREATE>>
            ~(TEMPORARY | TEMP)>>
            TABLE>>
            ~if_not_exists>>
            ~schema_name>>
            table_name>>
            (L_PAREN >>  column_def.sep_by(COMMA) + ~(COMMA >> table_constraint.sep_by(COMMA)) // R_PAREN) | (AS >> select_stmt)>>
            ~table_options>>
            ~SEMICOLON
        )
    

create_view_stmt = (   
            CREATE>>
            ~(TEMPORARY | TEMP)>>
            VIEW>>
            ~if_not_exists>>
            ~schema_name>>
            table_name>>
            ~(L_PAREN >> var.sep_by(COMMA) // R_PAREN)>>
            AS>>
            select_stmt>>
            ~SEMICOLON
        )
    

create_virtual_table_stmt = (
            CREATE>>
            VIRTUAL>>
            TABLE>>
            ~if_not_exists>>
            ~schema_name>>
            table_name>>
            USING>>
            var>>
            ~(L_PAREN >> var.sep_by(COMMA) // R_PAREN)>>
            ~SEMICOLON
        )

delete_stmt = (
            WITH >> ~(RECURSIVE >> common_table_expression.sep_by(COMMA))>>
            DELETE>>
            ~FROM>>
            qualified_table_name>>
            ~(WHERE >> expr)>>
            ~returning_clause>>
            ~SEMICOLON
        )
    

delete_stmt_limited = (
            WITH >> ~(RECURSIVE >> common_table_expression.sep_by(COMMA))>>
            DELETE>>
            ~FROM>>
            qualified_table_name>>
            ~(WHERE >> expr)>>
            ~returning_clause>>
            ORDER_BY >> ordering_term.sep_by(COMMA)>>
            LIMIT >> expr >> ~((OFFSET >> expr) | (COMMA >> expr))>>
            ~SEMICOLON
        )

detach_stmt = (
            DETACH>>
            ~DATABASE>>
            schema_name>>
            ~SEMICOLON
        )


drop_index_stmt = (
            DROP>>
            INDEX>>
            ~if_exists>>
            ~schema_name>>
            index_name>>
            ~SEMICOLON
        )
    

drop_table_stmt = (
            DROP>>
            TABLE>>
            ~if_exists>>
            ~schema_name>>
            table_name>>
            ~SEMICOLON
        )
    

drop_view_stmt = (
            DROP>>
            VIEW>>
            ~if_exists>>
            ~schema_name>>
            view_name>>
            ~SEMICOLON
        )
    

drop_trigger_stmt = (
            DROP>>
            TRIGGER>>
            ~if_exists>>
            ~schema_name>>
            trigger_name>>
            ~SEMICOLON
        )
    

insert_stmt =(
            WITH >> ~(RECURSIVE >> common_table_expression.sep_by(COMMA))>>
            REPLACE | (INSERT >> ~(OR >> (ABORT | IGNORE | FAIL | REPLACE | ROLLBACK)))>>
            INTO>>
            ~schema_name>>
            table_name>>
            ~(AS >> var)>>
            ~(L_PAREN >> var.sep_by(COMMA) // R_PAREN)>>
            ~(VALUES >> expr.parens(COMMA, L_PAREN, R_PAREN).sep_by(COMMA) >> ~upsert_clause)>>
            ~(select_stmt >> ~upsert_clause)>>
            ~(DEFAULT >> VALUES)>>
            ~returning_clause>>
            ~SEMICOLON
        )
    

pragma_stmt = (
            PRAGMA>>
            ~schema_name>>
            var>>
            ~EQ>>
            ~((EQ >> (var | signed_number | literal_value)) | (var | signed_number | literal_value).between(L_PAREN, R_PAREN))>>
            ~SEMICOLON
        )

reindex_stmt = (
            REINDEX>>
            ~schema_name>>
            index_name>>
            ~SEMICOLON
        )
    

release_stmt = (
            RELEASE>>
            SAVEPOINT>>
            var>>
            ~SEMICOLON
        )
    

rollback_stmt = (
            ROLLBACK>>
            ~TRANSACTION>>
            ~TO>>
            ~SAVEPOINT>>
            ~(var // SEMICOLON)
        )

savepoint_stmt =(
            SAVEPOINT>>
            var>>
            ~SEMICOLON
        )
    



vacuum_stmt = (
            VACUUM>>
            ~var>>
            ~(INTO >> var)>>
            ~SEMICOLON
        )


create_trigger_stmt = (
            CREATE>>
            ~(TEMPORARY | TEMP)>>
            TRIGGER>>
            ~if_not_exists>>
            ~schema_name>>
            trigger_name>>
            BEFORE | AFTER | (INSTEAD >> OF)>>
            INSERT | DELETE | (UPDATE >> ~(OF >> var.sep_by(COMMA)))>>
            ON>>
            table_name>>
            ~for_each_row>>
            ~(WHEN >> expr)>>
            BEGIN>>
            ((update_stmt | insert_stmt | delete_stmt | select_stmt)>>SEMICOLON).many()>>
            END>>
            ~SEMICOLON
        )

raise_function = RAISE >> (IGNORE | ((ROLLBACK | FAIL | ABORT) >> COMMA >> expr))

aggregate_function_invocation = function_name >> (~STAR 
                                                  | expr 
                                                  | (~DISTINCT >> expr.sep_by(COMMA) >> ~(ORDER_BY >> ordering_term.sep_by(COMMA)))
                                                  ).between(L_PAREN, R_PAREN) >> ~filter_clause


sql_stmt = choice(
    alter_table_stmt,
    analyze_stmt,
    attach_stmt,
    begin_stmt,

    commit_stmt,
    create_index_stmt,    
    create_table_stmt,
    create_trigger_stmt,
    create_view_stmt,
    create_virtual_table_stmt,
    
    delete_stmt,
    delete_stmt_limited,
    detach_stmt,
    drop_index_stmt,
    drop_table_stmt,
    drop_trigger_stmt,
    drop_view_stmt,
    
    insert_stmt,
    pragma_stmt,
    reindex_stmt,
    release_stmt,
    rollback_stmt,
    savepoint_stmt,
    select_stmt,
    update_stmt,
    update_stmt_limited,
    vacuum_stmt,
)
    
if __name__ == "__main__":
    print("__all__ =", [str(token.name) for token in TokenType])
    for token in TokenType:
        print(f"{token.name} = lift({token})")

