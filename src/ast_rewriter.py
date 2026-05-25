from typing import List

from pglast import parse_sql
from pglast.visitors import Visitor
from pglast.ast import A_Star, FuncCall, RangeVar, ResTarget, ColumnRef, SelectStmt, RangeSubselect, Alias, String
from pglast.stream import RawStream
import datetime


class AstRewriter(Visitor):
    def __init__(self, window_start: datetime.datetime, window_end: datetime.datetime, schema: dict):
        super().__init__()
        self.window_start = window_start
        self.window_end = window_end
        self.schema = schema

    def visit_RangeVar(self, ancestors, node):
        # print("visit_RangeVar")
        # print(node)
        if node.relname in self.schema:
            return RangeSubselect(
                subquery=parse_sql(scan(
                    node.relname, self.schema[node.relname], self.window_start, self.window_end))[0],
                alias=node.alias if node.alias else Alias(
                    aliasname=node.relname)
            )

    def visit_SelectStmt(self, ancestors, node):
        """We don't accept A_Star"""
        # print("visit_SelectStmt")
        target_list = list(node.targetList or [])

        if node.groupClause:
            val = FuncCall(
                funcname=(String("add_annotations"),),
                args=(ColumnRef(fields=["annotation"]),)
            )
        else:
            val = ColumnRef(fields=["annotation"])

        target_list.append(
            ResTarget(
                name="annotation",
                val=val
            )
        )
        node.targetList = tuple(target_list)

    def visit_JoinExpr(self, ancestors, node):
        left_name = node.larg.alias if node.larg.alias else node.larg.relname
        right_name = node.rarg.alias if node.rarg.alias else node.rarg.relname

        select_node = ancestors
        while select_node is not None and not isinstance(select_node.node, SelectStmt):
            select_node = select_node.parent
        # print(select_node.node)
        # print("ancestors------------------------------------")
        select_node = select_node.node

        new_targets = []
        for t in (select_node.targetList or []):
            col = t.val.fields[-1] if hasattr(t.val, 'fields') else None
            if t.name == "annotation" or col == "annotation":
                join_func = FuncCall(
                    funcname=(String("join_annotations"),),
                    args=(
                        ColumnRef(fields=(left_name, "annotation")),
                        ColumnRef(fields=(right_name, "annotation")),
                    )
                )

                if isinstance(t.val, FuncCall) and t.val.funcname[0].sval == "add_annotations":
                    t.val.args = (join_func,)
                    new_targets.append(t)
                else:
                    new_targets.append(ResTarget(
                        name="annotation",
                        val=join_func
                    ))
            else:
                new_targets.append(t)

        select_node.targetList = tuple(new_targets)


def rewrite_sql(sql: str, window_start: datetime.datetime, window_end: datetime.datetime, schema: dict) -> str:
    tree = parse_sql(sql)[0].stmt
    AstRewriter(window_start, window_end, schema)(tree)
    return RawStream()(tree)


def scan(table_name, columns, window_start, window_end):
    """
    AKA the annotate function
    For alive tuples A(t): birth <= window end AND death > window end
    Build the annotations, based on 'birth' log entry and time, and death log entry and time
    Tuples are annotated with [[{'birth': [w], 'death': [x], 'interval': [y, z]}]]
    1 annotation per a in A(t)
    'columns' should not include 'id' or 'death' as they have served their purpose to associate log entries to tuples
    This is exactly the same as the scan function in cte_rewriter at the moment
    """
    cols = ", ".join(columns)

    return f"""
            SELECT {cols}, jsonb_build_array(jsonb_agg(annotate(tmp.birth_id, tmp.birth_ts, b.death_id, b.death_ts) ORDER BY tmp.birth_ts)) AS annotation                                 -- tuples alive in the window, with birth and death log entries
            FROM (
                SELECT *                                            -- tuples alive in the window AKA died after window start, unable to remove tuples born after the window yet
                FROM {table_name} t
                LEFT JOIN (                                         -- assigns NULL to born before window
                    SELECT row_id, id as birth_id, ts as birth_ts   -- birth log entries after window start
                    FROM audit_log_pos a
                    WHERE a.table_name = '{table_name}'
                        AND a.ts >= '{window_start}'
                ) AS a ON a.row_id = t.id
                WHERE t.death > '{window_start}'                    -- eliminates tuples dead before window start
                    AND (a.birth_ts IS NULL                         -- eliminates tuples born after window end
                        OR a.birth_ts <= '{window_end}')        
            ) AS tmp
            LEFT JOIN (                                             -- attach death logs
                SELECT row_id, id as death_id, ts as death_ts       -- the log entries for deaths in the window
                FROM audit_log_neg b
                WHERE b.table_name = '{table_name}'
                    AND b.ts <= '{window_end}'
                    AND b.ts > '{window_start}'                     -- dying @ window start means it was never alive in the window, so don't care
            ) AS b ON b.row_id = tmp.id
            GROUP BY {cols}
            """
