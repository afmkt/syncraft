"""
A collection of parsers for SQL grammar using the syncraft library.
https://www.sqlite.org/syntaxdiagrams.html
"""
from __future__ import annotations
from typing import Any
from syncraft.syntax import Syntax
from sqlglot import TokenType

def lift(token_type: TokenType | str) -> Syntax[Any, Any]:
    if isinstance(token_type, str):
        return Syntax.token(text=token_type)
    else:
        return Syntax.token(token_type=token_type)
lazy = Syntax.lazy
token = Syntax.token
choice = Syntax.choice

L_PAREN = lift(TokenType.L_PAREN)
R_PAREN = lift(TokenType.R_PAREN)
COMMA = lift(TokenType.COMMA)
DOT = lift(TokenType.DOT)
DASH = lift(TokenType.DASH)
PLUS = lift(TokenType.PLUS)
COLON = lift(TokenType.COLON)
SEMICOLON = lift(TokenType.SEMICOLON)
STAR = lift(TokenType.STAR)
SLASH = lift(TokenType.SLASH)
LT = lift(TokenType.LT)
LTE = lift(TokenType.LTE)
GT = lift(TokenType.GT)
GTE = lift(TokenType.GTE)
NOT = lift(TokenType.NOT)
EQ = lift(TokenType.EQ)
NEQ = lift(TokenType.NEQ)
AND = lift(TokenType.AND)
OR = lift(TokenType.OR)
PARAMETER = lift(TokenType.PARAMETER)
DATABASE = lift(TokenType.DATABASE)
COLUMN = lift(TokenType.COLUMN)
TABLE = lift(TokenType.TABLE)
BLOB = lift(TokenType.BLOB)
ALIAS = lift(TokenType.ALIAS)
ALTER = lift(TokenType.ALTER)
ALL = lift(TokenType.ALL)
ASC = lift(TokenType.ASC)
ATTACH = lift(TokenType.ATTACH)
AUTO_INCREMENT = lift(TokenType.AUTO_INCREMENT)
BEGIN = lift(TokenType.BEGIN)
BETWEEN = lift(TokenType.BETWEEN)
CASE = lift(TokenType.CASE)
COLLATE = lift(TokenType.COLLATE)
COMMIT = lift(TokenType.COMMIT)
CONSTRAINT = lift(TokenType.CONSTRAINT)
CREATE = lift(TokenType.CREATE)
CROSS = lift(TokenType.CROSS)
CURRENT_DATE = lift(TokenType.CURRENT_DATE)
CURRENT_TIME = lift(TokenType.CURRENT_TIME)
CURRENT_TIMESTAMP = lift(TokenType.CURRENT_TIMESTAMP)
DEFAULT = lift(TokenType.DEFAULT)
DELETE = lift(TokenType.DELETE)
DESC = lift(TokenType.DESC)
DETACH = lift(TokenType.DETACH)
DISTINCT = lift(TokenType.DISTINCT)
DROP = lift(TokenType.DROP)
ELSE = lift(TokenType.ELSE)
END = lift(TokenType.END)
ESCAPE = lift(TokenType.ESCAPE)
EXCEPT = lift(TokenType.EXCEPT)
EXISTS = lift(TokenType.EXISTS)
FALSE = lift(TokenType.FALSE)
FILTER = lift(TokenType.FILTER)
FIRST = lift(TokenType.FIRST)
FOR = lift(TokenType.FOR)
FROM = lift(TokenType.FROM)
FULL = lift(TokenType.FULL)
GLOB = lift(TokenType.GLOB)
HAVING = lift(TokenType.HAVING)
IGNORE = lift(TokenType.IGNORE)

IN = lift(TokenType.IN)
INDEX = lift(TokenType.INDEX)
INNER = lift(TokenType.INNER)
INSERT = lift(TokenType.INSERT)
INTERSECT = lift(TokenType.INTERSECT)

INTO = lift(TokenType.INTO)
IS = lift(TokenType.IS)
ISNULL = lift(TokenType.ISNULL)
JOIN = lift(TokenType.JOIN)
KEY = lift(TokenType.KEY)
LEFT = lift(TokenType.LEFT)
LIKE = lift(TokenType.LIKE)

LIMIT = lift(TokenType.LIMIT)
NATURAL = lift(TokenType.NATURAL)
NOTHING = lift(TokenType.NOTHING)
NOTNULL = lift(TokenType.NOTNULL)
NULL = lift(TokenType.NULL)
OFFSET = lift(TokenType.OFFSET)
ON = lift(TokenType.ON)
ORDER_BY = lift(TokenType.ORDER_BY)
OUTER = lift(TokenType.OUTER)
OVER = lift(TokenType.OVER)
PARTITION = lift(TokenType.PARTITION)
PLACEHOLDER = lift(TokenType.PLACEHOLDER)
PRAGMA = lift(TokenType.PRAGMA)
RANGE = lift(TokenType.RANGE)
RECURSIVE = lift(TokenType.RECURSIVE)
RENAME = lift(TokenType.RENAME)
REPLACE = lift(TokenType.REPLACE)
RETURNING = lift(TokenType.RETURNING)
REFERENCES = lift(TokenType.REFERENCES)
RIGHT = lift(TokenType.RIGHT)
ROLLBACK = lift(TokenType.ROLLBACK)
ROW = lift(TokenType.ROW)
ROWS = lift(TokenType.ROWS)
SELECT = lift(TokenType.SELECT)
SET = lift(TokenType.SET)
TEMPORARY = lift(TokenType.TEMPORARY)    
THEN = lift(TokenType.THEN)
TRUE = lift(TokenType.TRUE)
UNION = lift(TokenType.UNION)
UPDATE = lift(TokenType.UPDATE)
USING = lift(TokenType.USING)
VALUES = lift(TokenType.VALUES)
VIEW = lift(TokenType.VIEW)
WHEN = lift(TokenType.WHEN)
WHERE = lift(TokenType.WHERE)
WINDOW = lift(TokenType.WINDOW)
WITH = lift(TokenType.WITH)
UNIQUE = lift(TokenType.UNIQUE)
ANALYZE = lift(TokenType.ANALYZE)

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
    

