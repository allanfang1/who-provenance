"""General SQL rewriter by AST.

Injects a provenance `annotation` reference into SELECT queries, so results carry
lineage alongside each row. Every base table already has a real `annotation` column;
this rewriter's job is purely to propagate that column correctly through joins and
aggregation, not to synthesize it.

Propagation rules:
  - Row-preserving SELECT (output has one row per input row / per joined-input row):
    pass the `annotation` column through as-is (joined via join_annotations if the
    FROM clause has more than one relation).
  - Row-collapsing SELECT (GROUP BY present, DISTINCT / DISTINCT ON present, or a
    target list contains a call to an aggregate function used in genuinely
    aggregating position -- not as a window function, and not as an ordered-set/
    hypothetical-set aggregate misused bare): wrap `annotation` in
    `add_annotations(...)` to merge per-group. DISTINCT (with or without ON) is
    row-collapsing the same way GROUP BY is -- it can reduce many input rows to
    one output row -- so it must trigger the same merge, even with no GROUP BY
    and no aggregate call present.
  - Join: combine `annotation` from every table/aliased relation participating in the
    FROM clause's join tree via nested `join_annotations(...)` calls, left to right.
  - Join + aggregation together: the joined annotation is fed into `add_annotations`.

rewrite_sql() is the entry point and the only recommended way to use this module.

KNOWN LIMITATION (inherent to a syntax-only rewriter, documented rather than hidden):
Whether a bare function name is an aggregate is, in general, a catalog fact, not a
syntax fact -- Postgres itself only knows this after looking up pg_proc.prokind at
analysis time. `AGGREGATE_FUNCTIONS` below is a best-effort list of all *built-in*
aggregates as of PostgreSQL 16. Any user-defined aggregate not in this list, used
bare (no GROUP BY present) with no other aggregate in the target list, will be
mis-classified as row-preserving. If your schema uses custom aggregates, either
add their names to AGGREGATE_FUNCTIONS, or extend `_is_aggregate_name` to consult
a live catalog (see `_is_aggregate_name_via_catalog` stub at the bottom for a
psycopg2-based version).

KNOWN LIMITATION (narrower, syntax-only): a FROM-item that isn't itself a SELECT
(e.g. a bare `(VALUES ...) AS v(a, b)`) is treated like any other relation --
its alias is used to build a `v.annotation` / bare `annotation` reference -- but
the rewriter has no SELECT to descend into and add an `annotation` column inside
it. If such a FROM-item doesn't independently provide an `annotation` column,
the rewritten query will reference one that doesn't exist. Rare in practice;
call this out if your schema does this pattern.
"""

from pglast import parse_sql
from pglast.stream import RawStream
from pglast.ast import ColumnRef, FuncCall, JoinExpr, RangeVar, ResTarget, String, A_Star
from pglast.visitors import Visitor

ANNOTATION_COL = "annotation"

# All built-in PostgreSQL aggregate functions (general-purpose, statistical,
# ordered-set, hypothetical-set, grouping). Source: postgresql.org/docs/current/
# functions-aggregate.html. Ordered-set/hypothetical-set names (mode, percentile_cont,
# percentile_disc, rank, dense_rank, percent_rank, cume_dist) are only aggregates
# when used with WITHIN GROUP -- see _is_aggregate_call below, which checks that
# explicitly rather than trusting name membership alone for those.
AGGREGATE_FUNCTIONS = {
    "array_agg", "avg", "bit_and", "bit_or", "bit_xor", "bool_and", "bool_or",
    "count", "every", "json_agg", "jsonb_agg", "json_object_agg", "jsonb_object_agg",
    "max", "min", "range_agg", "range_intersect_agg", "string_agg", "sum", "xmlagg",
    "corr", "covar_pop", "covar_samp", "regr_avgx", "regr_avgy", "regr_count",
    "regr_intercept", "regr_r2", "regr_slope", "regr_sxx", "regr_sxy", "regr_syy",
    "stddev", "stddev_pop", "stddev_samp", "variance", "var_pop", "var_samp",
    "grouping",
}

# Names that are aggregates ONLY in their WITHIN GROUP (ordered-set / hypothetical-set)
# form. Bare (no WITHIN GROUP), they are either window functions (with OVER) or,
# with neither, not valid as plain calls in standard PostgreSQL at all.
WITHIN_GROUP_ONLY_AGGREGATES = {
    "mode", "percentile_cont", "percentile_disc",
    "rank", "dense_rank", "percent_rank", "cume_dist",
}


def _relation_name(node):
    """Best-effort display name for a FROM-item: alias if present, else base name."""
    if node.alias:
        return node.alias.aliasname
    if isinstance(node, RangeVar):
        return node.relname
    return None


def _collect_relation_names(node):
    """Walk a FROM-clause join tree (RangeVar / RangeSubselect / JoinExpr, arbitrarily
    nested) and return the participating relation names in left-to-right order."""
    if isinstance(node, JoinExpr):
        return _collect_relation_names(node.larg) + _collect_relation_names(node.rarg)
    name = _relation_name(node)
    return [name] if name else []


def _is_star_target(target):
    """True if this ResTarget is a bare `*` (SELECT * / SELECT t.*), i.e. a
    ColumnRef whose last field is A_Star."""
    return (
        isinstance(target.val, ColumnRef)
        and target.val.fields
        and isinstance(target.val.fields[-1], A_Star)
    )


def _select_star_exposes_annotation(node):
    """True if this SELECT's target list is (only) a `SELECT *`-style
    expansion over a FROM clause consisting of a single subquery -- i.e.
    the common TPC-DS wrapper shape `SELECT * FROM (subquery) WHERE
    rownum <= N`.

    In that shape there is no explicit `annotation` ResTarget for the
    ordinary idempotency guard (`t.name == ANNOTATION_COL`) to catch --
    `*` doesn't have a `name` -- but appending our own `annotation AS
    annotation` on top would duplicate the column the inner subquery
    will itself end up producing (once via `*`, once explicitly).

    Note this check does NOT require the inner subquery to already carry
    an `annotation` target: traversal is top-down, so when we visit this
    outer node the inner subquery hasn't been rewritten yet. Instead we
    rely on the rewriter's own invariant -- every SelectStmt this visitor
    reaches ends up with an `annotation` column -- so any subquery FROM
    -item will always end up supplying one, making an explicit one on
    the outer `SELECT *` redundant regardless of the inner query's
    current (pre-rewrite) state.

    We only recognize the simple, common case: a single FROM-item that
    is itself a subquery (RangeSubselect). If it isn't this exact
    pattern, we fall through to the normal append logic.
    """
    if not node.targetList or not all(_is_star_target(t) for t in node.targetList):
        return False

    from pglast import ast as pg_ast

    if len(node.fromClause or ()) != 1:
        return False
    from_item = node.fromClause[0]
    return isinstance(from_item, pg_ast.RangeSubselect) and isinstance(
        from_item.subquery, pg_ast.SelectStmt
    )


def _is_aggregate_call(func_call):
    """True if this specific FuncCall node is being used in row-collapsing
    (aggregating) position -- i.e. it will actually reduce multiple input rows
    to one, as opposed to being a window function (OVER present) which does
    not change the row count."""
    if not func_call.funcname:
        return False
    name = func_call.funcname[-1].sval.lower()

    # A window function call never collapses rows, regardless of the function
    # name -- this is what the original implementation missed for e.g.
    # `sum(x) OVER (...)`.
    if func_call.over is not None:
        return False

    if name in WITHIN_GROUP_ONLY_AGGREGATES:
        # Only aggregating when used with WITHIN GROUP; bare/other usage of
        # these names is either a window function (caught above) or invalid.
        return bool(func_call.agg_within_group)

    return name in AGGREGATE_FUNCTIONS


def _has_aggregate_call(target_list):
    """True if any target expression contains a call in aggregating position.

    This needs to look inside arbitrary nested expressions -- `1 + sum(x)`,
    `CASE WHEN ... THEN count(*) END`, `COALESCE(avg(x), 0)`, etc. -- not just
    top-level ResTarget values, since an aggregate can appear nested inside
    any expression shape. pglast's `ast.Node` objects use `__slots__` (no
    `__dict__`/`_fields`), but they ARE iterable: `for member in node` yields
    the node's field/attribute names, which is the same primitive pglast's
    own Visitor.iterate() uses internally. We use it here for a plain
    recursive walk rather than a full Visitor, since we need to stop
    descending at SelectStmt boundaries (a FuncCall belonging to a nested/
    correlated subquery is that subquery's own concern, handled separately
    when the main visitor reaches it -- it must not mark the outer query as
    aggregating).
    """
    from pglast import ast as pg_ast

    def walk(node):
        if node is None:
            return False
        if isinstance(node, pg_ast.SelectStmt):
            return False
        if isinstance(node, FuncCall):
            if _is_aggregate_call(node):
                return True
            return any(walk(a) for a in (node.args or ()))
        if isinstance(node, tuple):
            return any(walk(n) for n in node)
        if isinstance(node, pg_ast.Node):
            return any(walk(getattr(node, member)) for member in node)
        return False

    return any(walk(t.val) for t in target_list or ())


def _annotation_ref(relation_name=None):
    """A ColumnRef to `annotation`, optionally table-qualified."""
    fields = (relation_name, ANNOTATION_COL) if relation_name else (
        ANNOTATION_COL,)
    return ColumnRef(fields=fields)


def _joined_annotation_expr(relation_names):
    """Build (possibly nested) join_annotations(...) calls across N>=1 relations."""
    if len(relation_names) == 1:
        return _annotation_ref(relation_names[0])
    expr = _annotation_ref(relation_names[0])
    for name in relation_names[1:]:
        expr = FuncCall(
            funcname=(String("join_annotations"),),
            args=(expr, _annotation_ref(name)),
        )
    return expr


class AstRewriter(Visitor):
    """Appends an `annotation` target to every SELECT, propagating it correctly
    through joins and aggregation. Assumes every base table already has a real
    `annotation` column, so no table substitution is performed."""

    def visit_SelectStmt(self, ancestors, node):
        # Set-operation nodes (UNION/INTERSECT/EXCEPT) carry their branches in
        # `larg`/`rarg` and have no fromClause/targetList of their own; let the
        # default traversal descend into those branches instead.
        if node.op is not None and node.op.name != "SETOP_NONE":
            return

        # Idempotency guard: the default traversal will also reach this node's
        # own subselects (FROM-clause subqueries, CTEs) on its own, and may
        # revisit an already-annotated node in some traversal orders. Don't
        # double-append.
        if any(t.name == ANNOTATION_COL for t in node.targetList or ()):
            return

        # A second, distinct idempotency case: `SELECT * FROM (subquery)`
            # where the subquery already produces an `annotation` column. The
            # `*` will already re-expose it, so appending another explicit
            # `annotation AS annotation` here would just duplicate the column
            # under the same name rather than propagating anything new.
        if _select_star_exposes_annotation(node):
            return

        relation_names = []
        for from_item in node.fromClause or ():
            relation_names.extend(_collect_relation_names(from_item))

        if len(relation_names) > 1:
            annotation_expr = _joined_annotation_expr(relation_names)
        else:
            annotation_expr = _annotation_ref()

        # Row-collapsing if: GROUP BY is present, DISTINCT (or DISTINCT ON) is
        # present, or the target list contains a genuinely aggregating call.
        # Note on distinctClause: pglast/Postgres represents plain `DISTINCT`
        # as a tuple containing a single `None` (distinct on the whole row),
        # and `DISTINCT ON (...)` as a tuple of the ON expressions -- so
        # `bool(node.distinctClause)` is True for either form and False
        # (attribute is plain `None`) when there's no DISTINCT at all.
        is_aggregate = (
            bool(node.groupClause)
            or bool(node.distinctClause)
            or _has_aggregate_call(node.targetList)
        )
        if is_aggregate:
            annotation_expr = FuncCall(
                funcname=(String("add_annotations"),),
                args=(annotation_expr,),
            )

        target_list = list(node.targetList or [])
        target_list.append(ResTarget(name=ANNOTATION_COL, val=annotation_expr))
        node.targetList = tuple(target_list)


def rewrite_sql(sql_string: str) -> str:
    """Rewrite a SQL query so every SELECT carries a correctly-propagated
    `annotation` column, merging across joins and aggregations as needed.

    Args:
        sql_string: the input SQL query. All referenced base tables are assumed
            to already have a real `annotation` column.
    Returns:
        The rewritten SQL query as a string.
    """
    tree = parse_sql(sql_string)[0].stmt
    AstRewriter()(tree)
    return RawStream()(tree)


# ---------------------------------------------------------------------------
# Optional: catalog-backed aggregate detection, for schemas with user-defined
# aggregates that AGGREGATE_FUNCTIONS can't know about. Not wired in by
# default since it requires a live DB connection at rewrite time; swap
# `_is_aggregate_name` calls to use this if you need full correctness for
# custom aggregates.
# ---------------------------------------------------------------------------
def _load_aggregate_names_from_catalog(dsn: str) -> set:
    """Query pg_proc for every function currently registered as an aggregate
    (prokind = 'a'), including user-defined ones. Call once at startup /
    per-rewrite-batch and pass the result in place of AGGREGATE_FUNCTIONS.
    """
    import psycopg2

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT proname FROM pg_proc WHERE prokind = 'a'")
        return {row[0] for row in cur.fetchall()}
