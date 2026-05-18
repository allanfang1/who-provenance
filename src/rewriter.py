
class Rewriter:
    """CTE approach"""
    @staticmethod
    def build_cte(steps: list[tuple[str, str]], final_select: str) -> str:
        """
            steps: list of (cte_name, sql_string)
            final_select: what to SELECT from the last CTE, e.g. "SELECT * FROM step3" 
        """
        ctes = ",\n".join(f"{name} AS (\n  {sql}\n)" for name, sql in steps)
        return f"WITH {ctes}\n{final_select}"

    @staticmethod
    def scan(table_name, columns, window_start, window_end):
        """
        This is effectively the annotate function
        Tuples are annotated with [[x, y]] where x is audit entry of tuple creation and y is entry of deprecation (or INF if not deprecated)
        Columns should not include 'id' as tuple ids have finished serving their purpose to associate log entries to tuples
        """
        cols_no_id = [x for x in columns if x != "id"]
        cols_no_id = ", ".join(cols_no_id)

        cols = [f"tmp.{c}" for c in columns]
        cols = ", ".join(cols)
        return f"""
                SELECT {cols_no_id}, annotation
                FROM(
                    SELECT {cols}, jsonb_build_array(jsonb_agg(elem ORDER BY elem::numeric)) as annotation
                    FROM (
                        SELECT t.*, annotate(a.id, t.alive) AS annotation 
                        FROM {table_name} t 
                        FULL JOIN (
                            SELECT id, row_id
                            FROM audit_log
                            WHERE id >= {window_start}
                                AND table_name = '{table_name}'
                        ) AS a 
                            ON a.row_id = t.id 
                        WHERE a.id IS NULL OR a.id <= {window_end} -- TODO using a.id <= instead of a.ts <= for testing purposes
                    ) as tmp
                    CROSS JOIN LATERAL jsonb_array_elements(tmp.annotation) AS elem
                    GROUP BY {cols}
                ) sub
                """

    @staticmethod
    def selection(table_name, condition):
        """condition is a string like "name = 'Alice'" """
        return f"SELECT * FROM {table_name} WHERE {condition}"

    @staticmethod
    def projection(table_name, columns: list):
        """columns is a list of column names to project not including 'annotation' which is automatically included, e.g. ["name", "email"]"""
        columns.append("annotation")
        return f"SELECT {', '.join(columns)} FROM {table_name}"

    @staticmethod
    def join(t1, t1_columns: list, t2, t2_columns: list, join_condition):
        """t1_columns and t2_columns are lists of column names to project from each table, and join_condition is a string like "t1.id = t2.user_id"
        Assume columns are all columns except 'annotation'"""
        t1_cols = [f"t1.{c} AS t1_{c}" for c in t1_columns]
        t2_cols = [f"t2.{c} AS t2_{c}" for c in t2_columns]

        columns = ", ".join(t1_cols + t2_cols)
        return f"SELECT {columns}, join_annotations(t1.annotation, t2.annotation) as annotation FROM {t1} t1 JOIN {t2} t2 ON {join_condition}"

    @staticmethod
    def union_all(t1, t2):
        return f"SELECT * FROM {t1} t1 UNION ALL SELECT * FROM {t2} t2"

    @staticmethod
    def aggregate(table, columns: list):
        """Uses custom aggregate function to combine annotations"""
        cols = ", ".join(columns)
        return f"SELECT {cols}, add_annotations(annotation) AS annotation FROM {table} GROUP BY {cols}"

    @staticmethod
    def aggregate_min(table, columns: list):
        """Uses custom aggregate function to combine annotations"""
        cols = ", ".join(columns)
        return f"SELECT {cols}, add_annotations_min(annotation) AS annotation FROM {table} GROUP BY {cols}"

    @staticmethod
    def rename():
        pass
