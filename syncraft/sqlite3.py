"""
A collection of parsers for SQL grammar using the syncraft library.
https://www.sqlite.org/syntaxdiagrams.html
"""
from __future__ import annotations
from typing import Any
from syncraft.syntax import Syntax
from sqlglot import TokenType

lift = Syntax.lift
lazy = Syntax.lazy
token = Syntax.token
choice = Syntax.choice

L_PAREN = lift(TokenType.L_PAREN)
R_PAREN = lift(TokenType.R_PAREN)
L_BRACKET = lift(TokenType.L_BRACKET)
R_BRACKET = lift(TokenType.R_BRACKET)
L_BRACE = lift(TokenType.L_BRACE)
R_BRACE = lift(TokenType.R_BRACE)
COMMA = lift(TokenType.COMMA)
DOT = lift(TokenType.DOT)
DASH = lift(TokenType.DASH)
PLUS = lift(TokenType.PLUS)
COLON = lift(TokenType.COLON)
DOTCOLON = lift(TokenType.DOTCOLON)
DCOLON = lift(TokenType.DCOLON)
DQMARK = lift(TokenType.DQMARK)
SEMICOLON = lift(TokenType.SEMICOLON)
STAR = lift(TokenType.STAR)
BACKSLASH = lift(TokenType.BACKSLASH)
SLASH = lift(TokenType.SLASH)
LT = lift(TokenType.LT)
LTE = lift(TokenType.LTE)
GT = lift(TokenType.GT)
GTE = lift(TokenType.GTE)
NOT = lift(TokenType.NOT)
EQ = lift(TokenType.EQ)
NEQ = lift(TokenType.NEQ)
NULLSAFE_EQ = lift(TokenType.NULLSAFE_EQ)
COLON_EQ = lift(TokenType.COLON_EQ)
AND = lift(TokenType.AND)
OR = lift(TokenType.OR)
AMP = lift(TokenType.AMP)
DPIPE = lift(TokenType.DPIPE)
PIPE_GT = lift(TokenType.PIPE_GT)
PIPE = lift(TokenType.PIPE)
PIPE_SLASH = lift(TokenType.PIPE_SLASH)
DPIPE_SLASH = lift(TokenType.DPIPE_SLASH)
CARET = lift(TokenType.CARET)
CARET_AT = lift(TokenType.CARET_AT)
TILDA = lift(TokenType.TILDA)
ARROW = lift(TokenType.ARROW)
DARROW = lift(TokenType.DARROW)
FARROW = lift(TokenType.FARROW)
HASH = lift(TokenType.HASH)
HASH_ARROW = lift(TokenType.HASH_ARROW)
DHASH_ARROW = lift(TokenType.DHASH_ARROW)
LR_ARROW = lift(TokenType.LR_ARROW)
DAT = lift(TokenType.DAT)
LT_AT = lift(TokenType.LT_AT)
AT_GT = lift(TokenType.AT_GT)
DOLLAR = lift(TokenType.DOLLAR)
PARAMETER = lift(TokenType.PARAMETER)
SESSION_PARAMETER = lift(TokenType.SESSION_PARAMETER)
DAMP = lift(TokenType.DAMP)
XOR = lift(TokenType.XOR)
DSTAR = lift(TokenType.DSTAR)
URI_START = lift(TokenType.URI_START)
BLOCK_START = lift(TokenType.BLOCK_START)
BLOCK_END = lift(TokenType.BLOCK_END)
SPACE = lift(TokenType.SPACE)
BREAK = lift(TokenType.BREAK)
STRING = lift(TokenType.STRING)
NUMBER = lift(TokenType.NUMBER)
IDENTIFIER = lift(TokenType.IDENTIFIER)
DATABASE = lift(TokenType.DATABASE)
COLUMN = lift(TokenType.COLUMN)
COLUMN_DEF = lift(TokenType.COLUMN_DEF)
SCHEMA = lift(TokenType.SCHEMA)
TABLE = lift(TokenType.TABLE)
WAREHOUSE = lift(TokenType.WAREHOUSE)
STAGE = lift(TokenType.STAGE)
STREAMLIT = lift(TokenType.STREAMLIT)
VAR = lift(TokenType.VAR)
BIT_STRING = lift(TokenType.BIT_STRING)
HEX_STRING = lift(TokenType.HEX_STRING)
BYTE_STRING = lift(TokenType.BYTE_STRING)
NATIONAL_STRING = lift(TokenType.NATIONAL_STRING)
RAW_STRING = lift(TokenType.RAW_STRING)
HEREDOC_STRING = lift(TokenType.HEREDOC_STRING)
UNICODE_STRING = lift(TokenType.UNICODE_STRING)
BIT = lift(TokenType.BIT)
BOOLEAN = lift(TokenType.BOOLEAN)
TINYINT = lift(TokenType.TINYINT)
UTINYINT = lift(TokenType.UTINYINT)
SMALLINT = lift(TokenType.SMALLINT)
USMALLINT = lift(TokenType.USMALLINT)
MEDIUMINT = lift(TokenType.MEDIUMINT)
UMEDIUMINT = lift(TokenType.UMEDIUMINT)
INT = lift(TokenType.INT)
UINT = lift(TokenType.UINT)
BIGINT = lift(TokenType.BIGINT)
UBIGINT = lift(TokenType.UBIGINT)
INT128 = lift(TokenType.INT128)
UINT128 = lift(TokenType.UINT128)
INT256 = lift(TokenType.INT256)
UINT256 = lift(TokenType.UINT256)
FLOAT = lift(TokenType.FLOAT)
DOUBLE = lift(TokenType.DOUBLE)
UDOUBLE = lift(TokenType.UDOUBLE)
DECIMAL = lift(TokenType.DECIMAL)
DECIMAL32 = lift(TokenType.DECIMAL32)
DECIMAL64 = lift(TokenType.DECIMAL64)
DECIMAL128 = lift(TokenType.DECIMAL128)
DECIMAL256 = lift(TokenType.DECIMAL256)
UDECIMAL = lift(TokenType.UDECIMAL)
BIGDECIMAL = lift(TokenType.BIGDECIMAL)
CHAR = lift(TokenType.CHAR)
NCHAR = lift(TokenType.NCHAR)
VARCHAR = lift(TokenType.VARCHAR)
NVARCHAR = lift(TokenType.NVARCHAR)
BPCHAR = lift(TokenType.BPCHAR)
TEXT = lift(TokenType.TEXT)
MEDIUMTEXT = lift(TokenType.MEDIUMTEXT)
LONGTEXT = lift(TokenType.LONGTEXT)
BLOB = lift(TokenType.BLOB)
MEDIUMBLOB = lift(TokenType.MEDIUMBLOB)
LONGBLOB = lift(TokenType.LONGBLOB)
TINYBLOB = lift(TokenType.TINYBLOB)
TINYTEXT = lift(TokenType.TINYTEXT)
NAME = lift(TokenType.NAME)
BINARY = lift(TokenType.BINARY)
VARBINARY = lift(TokenType.VARBINARY)
JSON = lift(TokenType.JSON)
JSONB = lift(TokenType.JSONB)
TIME = lift(TokenType.TIME)
TIMETZ = lift(TokenType.TIMETZ)
TIMESTAMP = lift(TokenType.TIMESTAMP)
TIMESTAMPTZ = lift(TokenType.TIMESTAMPTZ)
TIMESTAMPLTZ = lift(TokenType.TIMESTAMPLTZ)
TIMESTAMPNTZ = lift(TokenType.TIMESTAMPNTZ)
TIMESTAMP_S = lift(TokenType.TIMESTAMP_S)
TIMESTAMP_MS = lift(TokenType.TIMESTAMP_MS)
TIMESTAMP_NS = lift(TokenType.TIMESTAMP_NS)
DATETIME = lift(TokenType.DATETIME)
DATETIME2 = lift(TokenType.DATETIME2)
DATETIME64 = lift(TokenType.DATETIME64)
SMALLDATETIME = lift(TokenType.SMALLDATETIME)
DATE = lift(TokenType.DATE)
DATE32 = lift(TokenType.DATE32)
INT4RANGE = lift(TokenType.INT4RANGE)
INT4MULTIRANGE = lift(TokenType.INT4MULTIRANGE)
INT8RANGE = lift(TokenType.INT8RANGE)
INT8MULTIRANGE = lift(TokenType.INT8MULTIRANGE)
NUMRANGE = lift(TokenType.NUMRANGE)
NUMMULTIRANGE = lift(TokenType.NUMMULTIRANGE)
TSRANGE = lift(TokenType.TSRANGE)
TSMULTIRANGE = lift(TokenType.TSMULTIRANGE)
TSTZRANGE = lift(TokenType.TSTZRANGE)
TSTZMULTIRANGE = lift(TokenType.TSTZMULTIRANGE)
DATERANGE = lift(TokenType.DATERANGE)
DATEMULTIRANGE = lift(TokenType.DATEMULTIRANGE)
UUID = lift(TokenType.UUID)
GEOGRAPHY = lift(TokenType.GEOGRAPHY)
NULLABLE = lift(TokenType.NULLABLE)
GEOMETRY = lift(TokenType.GEOMETRY)
POINT = lift(TokenType.POINT)
RING = lift(TokenType.RING)
LINESTRING = lift(TokenType.LINESTRING)
MULTILINESTRING = lift(TokenType.MULTILINESTRING)
POLYGON = lift(TokenType.POLYGON)
MULTIPOLYGON = lift(TokenType.MULTIPOLYGON)
HLLSKETCH = lift(TokenType.HLLSKETCH)
HSTORE = lift(TokenType.HSTORE)
SUPER = lift(TokenType.SUPER)
SERIAL = lift(TokenType.SERIAL)
SMALLSERIAL = lift(TokenType.SMALLSERIAL)
BIGSERIAL = lift(TokenType.BIGSERIAL)
XML = lift(TokenType.XML)
YEAR = lift(TokenType.YEAR)
USERDEFINED = lift(TokenType.USERDEFINED)
MONEY = lift(TokenType.MONEY)
SMALLMONEY = lift(TokenType.SMALLMONEY)
ROWVERSION = lift(TokenType.ROWVERSION)
IMAGE = lift(TokenType.IMAGE)
VARIANT = lift(TokenType.VARIANT)
OBJECT = lift(TokenType.OBJECT)
INET = lift(TokenType.INET)
IPADDRESS = lift(TokenType.IPADDRESS)
IPPREFIX = lift(TokenType.IPPREFIX)
IPV4 = lift(TokenType.IPV4)
IPV6 = lift(TokenType.IPV6)
ENUM = lift(TokenType.ENUM)
ENUM8 = lift(TokenType.ENUM8)
ENUM16 = lift(TokenType.ENUM16)
FIXEDSTRING = lift(TokenType.FIXEDSTRING)
LOWCARDINALITY = lift(TokenType.LOWCARDINALITY)
NESTED = lift(TokenType.NESTED)
AGGREGATEFUNCTION = lift(TokenType.AGGREGATEFUNCTION)
SIMPLEAGGREGATEFUNCTION = lift(TokenType.SIMPLEAGGREGATEFUNCTION)
TDIGEST = lift(TokenType.TDIGEST)
UNKNOWN = lift(TokenType.UNKNOWN)
VECTOR = lift(TokenType.VECTOR)
DYNAMIC = lift(TokenType.DYNAMIC)
VOID = lift(TokenType.VOID)
ALIAS = lift(TokenType.ALIAS)
ALTER = lift(TokenType.ALTER)
ALL = lift(TokenType.ALL)
ANTI = lift(TokenType.ANTI)
ANY = lift(TokenType.ANY)
APPLY = lift(TokenType.APPLY)
ARRAY = lift(TokenType.ARRAY)
ASC = lift(TokenType.ASC)
ASOF = lift(TokenType.ASOF)
ATTACH = lift(TokenType.ATTACH)
AUTO_INCREMENT = lift(TokenType.AUTO_INCREMENT)
BEGIN = lift(TokenType.BEGIN)
BETWEEN = lift(TokenType.BETWEEN)
BULK_COLLECT_INTO = lift(TokenType.BULK_COLLECT_INTO)
CACHE = lift(TokenType.CACHE)
CASE = lift(TokenType.CASE)
CHARACTER_SET = lift(TokenType.CHARACTER_SET)
CLUSTER_BY = lift(TokenType.CLUSTER_BY)
COLLATE = lift(TokenType.COLLATE)
COMMAND = lift(TokenType.COMMAND)
COMMENT = lift(TokenType.COMMENT)
COMMIT = lift(TokenType.COMMIT)
CONNECT_BY = lift(TokenType.CONNECT_BY)
CONSTRAINT = lift(TokenType.CONSTRAINT)
COPY = lift(TokenType.COPY)
CREATE = lift(TokenType.CREATE)
CROSS = lift(TokenType.CROSS)
CUBE = lift(TokenType.CUBE)
CURRENT_DATE = lift(TokenType.CURRENT_DATE)
CURRENT_DATETIME = lift(TokenType.CURRENT_DATETIME)
CURRENT_SCHEMA = lift(TokenType.CURRENT_SCHEMA)
CURRENT_TIME = lift(TokenType.CURRENT_TIME)
CURRENT_TIMESTAMP = lift(TokenType.CURRENT_TIMESTAMP)
CURRENT_USER = lift(TokenType.CURRENT_USER)
DECLARE = lift(TokenType.DECLARE)
DEFAULT = lift(TokenType.DEFAULT)
DELETE = lift(TokenType.DELETE)
DESC = lift(TokenType.DESC)
DESCRIBE = lift(TokenType.DESCRIBE)
DETACH = lift(TokenType.DETACH)
DICTIONARY = lift(TokenType.DICTIONARY)
DISTINCT = lift(TokenType.DISTINCT)
DISTRIBUTE_BY = lift(TokenType.DISTRIBUTE_BY)
DIV = lift(TokenType.DIV)
DROP = lift(TokenType.DROP)
ELSE = lift(TokenType.ELSE)
END = lift(TokenType.END)
ESCAPE = lift(TokenType.ESCAPE)
EXCEPT = lift(TokenType.EXCEPT)
EXECUTE = lift(TokenType.EXECUTE)
EXISTS = lift(TokenType.EXISTS)
FALSE = lift(TokenType.FALSE)
FETCH = lift(TokenType.FETCH)
FILE_FORMAT = lift(TokenType.FILE_FORMAT)
FILTER = lift(TokenType.FILTER)
FINAL = lift(TokenType.FINAL)
FIRST = lift(TokenType.FIRST)
FOR = lift(TokenType.FOR)
FORCE = lift(TokenType.FORCE)
FOREIGN_KEY = lift(TokenType.FOREIGN_KEY)
FORMAT = lift(TokenType.FORMAT)
FROM = lift(TokenType.FROM)
FULL = lift(TokenType.FULL)
FUNCTION = lift(TokenType.FUNCTION)
GET = lift(TokenType.GET)
GLOB = lift(TokenType.GLOB)
GLOBAL = lift(TokenType.GLOBAL)
GRANT = lift(TokenType.GRANT)
GROUP_BY = lift(TokenType.GROUP_BY)
GROUPING_SETS = lift(TokenType.GROUPING_SETS)
HAVING = lift(TokenType.HAVING)
HINT = lift(TokenType.HINT)
IGNORE = lift(TokenType.IGNORE)
ILIKE = lift(TokenType.ILIKE)

IN = lift(TokenType.IN)
INDEX = lift(TokenType.INDEX)
INNER = lift(TokenType.INNER)
INSERT = lift(TokenType.INSERT)
INTERSECT = lift(TokenType.INTERSECT)
INTERVAL = lift(TokenType.INTERVAL)
INTO = lift(TokenType.INTO)
INTRODUCER = lift(TokenType.INTRODUCER)
IRLIKE = lift(TokenType.IRLIKE)
IS = lift(TokenType.IS)
ISNULL = lift(TokenType.ISNULL)
JOIN = lift(TokenType.JOIN)
JOIN_MARKER = lift(TokenType.JOIN_MARKER)
KEEP = lift(TokenType.KEEP)
KEY = lift(TokenType.KEY)
KILL = lift(TokenType.KILL)
LANGUAGE = lift(TokenType.LANGUAGE)
LATERAL = lift(TokenType.LATERAL)
LEFT = lift(TokenType.LEFT)
LIKE = lift(TokenType.LIKE)

LIMIT = lift(TokenType.LIMIT)
LIST = lift(TokenType.LIST)
LOAD = lift(TokenType.LOAD)
LOCK = lift(TokenType.LOCK)
MAP = lift(TokenType.MAP)
MATCH_CONDITION = lift(TokenType.MATCH_CONDITION)
MATCH_RECOGNIZE = lift(TokenType.MATCH_RECOGNIZE)
MEMBER_OF = lift(TokenType.MEMBER_OF)
MERGE = lift(TokenType.MERGE)
MOD = lift(TokenType.MOD)
MODEL = lift(TokenType.MODEL)
NATURAL = lift(TokenType.NATURAL)
NEXT = lift(TokenType.NEXT)
NOTHING = lift(TokenType.NOTHING)
NOTNULL = lift(TokenType.NOTNULL)
NULL = lift(TokenType.NULL)
OBJECT_IDENTIFIER = lift(TokenType.OBJECT_IDENTIFIER)
OFFSET = lift(TokenType.OFFSET)
ON = lift(TokenType.ON)
ONLY = lift(TokenType.ONLY)
OPERATOR = lift(TokenType.OPERATOR)
ORDER_BY = lift(TokenType.ORDER_BY)
ORDER_SIBLINGS_BY = lift(TokenType.ORDER_SIBLINGS_BY)
ORDERED = lift(TokenType.ORDERED)
ORDINALITY = lift(TokenType.ORDINALITY)
OUTER = lift(TokenType.OUTER)
OVER = lift(TokenType.OVER)
OVERLAPS = lift(TokenType.OVERLAPS)
OVERWRITE = lift(TokenType.OVERWRITE)
PARTITION = lift(TokenType.PARTITION)
PARTITION_BY = lift(TokenType.PARTITION_BY)
PERCENT = lift(TokenType.PERCENT)
PIVOT = lift(TokenType.PIVOT)
PLACEHOLDER = lift(TokenType.PLACEHOLDER)
POSITIONAL = lift(TokenType.POSITIONAL)
PRAGMA = lift(TokenType.PRAGMA)
PREWHERE = lift(TokenType.PREWHERE)
PRIMARY_KEY = lift(TokenType.PRIMARY_KEY)
PROCEDURE = lift(TokenType.PROCEDURE)
PROPERTIES = lift(TokenType.PROPERTIES)
PSEUDO_TYPE = lift(TokenType.PSEUDO_TYPE)
PUT = lift(TokenType.PUT)
QUALIFY = lift(TokenType.QUALIFY)
QUOTE = lift(TokenType.QUOTE)
RANGE = lift(TokenType.RANGE)
RECURSIVE = lift(TokenType.RECURSIVE)
REFRESH = lift(TokenType.REFRESH)
RENAME = lift(TokenType.RENAME)
REPLACE = lift(TokenType.REPLACE)
RETURNING = lift(TokenType.RETURNING)
REFERENCES = lift(TokenType.REFERENCES)
RIGHT = lift(TokenType.RIGHT)
RLIKE = lift(TokenType.RLIKE)
ROLLBACK = lift(TokenType.ROLLBACK)
ROLLUP = lift(TokenType.ROLLUP)
ROW = lift(TokenType.ROW)
ROWS = lift(TokenType.ROWS)
SELECT = lift(TokenType.SELECT)
SEMI = lift(TokenType.SEMI)
SEPARATOR = lift(TokenType.SEPARATOR)
SEQUENCE = lift(TokenType.SEQUENCE)
SERDE_PROPERTIES = lift(TokenType.SERDE_PROPERTIES)
SET = lift(TokenType.SET)
SETTINGS = lift(TokenType.SETTINGS)
SHOW = lift(TokenType.SHOW)
SIMILAR_TO = lift(TokenType.SIMILAR_TO)
SOME = lift(TokenType.SOME)
SORT_BY = lift(TokenType.SORT_BY)
START_WITH = lift(TokenType.START_WITH)
STORAGE_INTEGRATION = lift(TokenType.STORAGE_INTEGRATION)
STRAIGHT_JOIN = lift(TokenType.STRAIGHT_JOIN)
STRUCT = lift(TokenType.STRUCT)
SUMMARIZE = lift(TokenType.SUMMARIZE)
TABLE_SAMPLE = lift(TokenType.TABLE_SAMPLE)
TAG = lift(TokenType.TAG)
TEMPORARY = lift(TokenType.TEMPORARY)    
TOP = lift(TokenType.TOP)
THEN = lift(TokenType.THEN)
TRUE = lift(TokenType.TRUE)
TRUNCATE = lift(TokenType.TRUNCATE)
UNCACHE = lift(TokenType.UNCACHE)
UNION = lift(TokenType.UNION)
UNNEST = lift(TokenType.UNNEST)
UNPIVOT = lift(TokenType.UNPIVOT)
UPDATE = lift(TokenType.UPDATE)
USE = lift(TokenType.USE)
USING = lift(TokenType.USING)
VALUES = lift(TokenType.VALUES)
VIEW = lift(TokenType.VIEW)
VOLATILE = lift(TokenType.VOLATILE)
WHEN = lift(TokenType.WHEN)
WHERE = lift(TokenType.WHERE)
WINDOW = lift(TokenType.WINDOW)
WITH = lift(TokenType.WITH)
UNIQUE = lift(TokenType.UNIQUE)
VERSION_SNAPSHOT = lift(TokenType.VERSION_SNAPSHOT)
TIMESTAMP_SNAPSHOT = lift(TokenType.TIMESTAMP_SNAPSHOT)
OPTION = lift(TokenType.OPTION)
SINK = lift(TokenType.SINK)
SOURCE = lift(TokenType.SOURCE)
ANALYZE = lift(TokenType.ANALYZE)
NAMESPACE = lift(TokenType.NAMESPACE)
EXPORT = lift(TokenType.EXPORT)
HIVE_TOKEN_STREAM = lift(TokenType.HIVE_TOKEN_STREAM)

ABORT = lift("ABORT")
FAIL = lift("FAIL")
LOOP = lift("LOOP")
WHILE = lift("WHILE")
TRIGGER  = lift("TRIGGER")
TEMP = lift("TEMP")
IF = lift("IF")

BEFORE = lift("BEFORE")
AFTER = lift("AFTER")
INSTEAD = lift("INSTEAD")
OF = lift("OF")
EACH = lift("EACH")

ADD = lift("ADD")
TO = lift("TO")
ALWAYS = lift("ALWAYS")
RAISE = lift("RAISE")
RETURNS = lift("RETURNS")
PRIMARY = lift("PRIMARY")
NULLS = lift("NULLS")
LAST = lift("LAST")
CONFLICT = lift("CONFLICT")
CHECK = lift("CHECK")
GENERATED = lift("GENERATED")
STORED = lift("STORED")
VIRTUAL = lift("VIRTUAL")
AS = ALIAS
CASCADE = lift("CASCADE")
RESTRICT = lift("RESTRICT")
NO = lift("NO")
ACTION = lift("ACTION")
NO_ACTION = NO >> ACTION
MATCH = lift("MATCH")
DEFERRABLE = lift("DEFERRABLE")
INITIALLY = lift("INITIALLY")
IMMEDIATE = lift("IMMEDIATE")
DEFERRED = lift("DEFERRED")
RELY = lift("RELY")
NORELY = lift("NORELY")
VALIDATE = lift("VALIDATE")
NOVALIDATE = lift("NOVALIDATE")
EXCLUSIVE = lift("EXCLUSIVE")
TRANSACTION = lift("TRANSACTION")
WITHOUT = lift("WITHOUT")
ROWID = lift("ROWID")
STRICT = lift("STRICT")
MATERIALIZED = lift("MATERIALIZED")
DO = lift("DO")
RELEASE = lift("RELEASE")
SAVEPOINT = lift("SAVEPOINT")
REINDEX = lift("REINDEX")
INDEXED = lift("INDEXED")
VACUUM = lift("VACUUM")
GROUP = lift("GROUP")
GROUPS = lift("GROUPS")
UNBOUNDED = lift("UNBOUNDED")
PRECEDING = lift("PRECEDING")
FOLLOWING = lift("FOLLOWING")
CURRENT = lift("CURRENT")
EXCLUDE = lift("EXCLUDE")
OTHERS = lift("OTHERS")
TIES = lift("TIES")
BY = lift("BY")
CAST = lift("CAST")
REGEXP = lift("REGEXP")

var = token(token_type=TokenType.VAR)
string = token(token_type=TokenType.STRING)
number = token(token_type=TokenType.NUMBER)

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

