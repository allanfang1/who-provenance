
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
        AKA the annotate function
        For alive tuples A(t): birth <= window end AND death > window end
        Build the annotations, based on 'birth' log entry and time, and death log entry and time
        Tuples are annotated with [[{'birth': [w], 'death': [x], 'interval': [y, z]}]]
        1 annotation per a in A(t)
        'columns' should not include 'id' or 'death' as they have served their purpose to associate log entries to tuples
        """
        cols_no_id = [x for x in columns if x != "id"]
        cols_no_id = ", ".join(cols_no_id)

        return f"""
                SELECT {cols_no_id}, jsonb_build_array(jsonb_agg(annotate(tmp.birth_id, tmp.birth_ts, b.death_id, b.death_ts) ORDER BY tmp.birth_ts)) AS annotation                                 -- tuples alive in the window, with birth and death log entries
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
                GROUP BY {cols_no_id}
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

    # @staticmethod
    # def aggregate_min(table, columns: list):
    #     """Uses custom aggregate function to combine annotations"""
    #     cols = ", ".join(columns)
    #     return f"SELECT {cols}, add_annotations_min(annotation) AS annotation FROM {table} GROUP BY {cols}"

    @staticmethod
    def rename():
        pass
