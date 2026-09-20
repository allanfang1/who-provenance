

-- Annotation + transition: Simple concatenation of annotation arrays
CREATE OR REPLACE FUNCTION annotations_union_trans(state jsonb, val jsonb) RETURNS jsonb AS $$
    SELECT state || val;
$$ LANGUAGE sql;


-- Annotation +: Custom aggregate
CREATE OR REPLACE AGGREGATE add_annotations(jsonb) ( -- TODO is there deduplication needed here?
    SFUNC = annotations_union_trans,
    STYPE = jsonb,
    INITCOND = '[]'
);


-- ANNOTATION *: Custom function to combine annotations from joins
--      Intersect the intervals
--          If intervals intersect, union birth and death sets
CREATE OR REPLACE FUNCTION join_annotations(a jsonb, b jsonb) RETURNS jsonb AS $$
DECLARE
    result      jsonb := '[]'::jsonb;
    a_group     jsonb;
    b_group     jsonb;
    a_elem      jsonb;
    b_elem      jsonb;
    a_start     timestamptz;
    a_end       timestamptz;
    b_start     timestamptz;
    b_end       timestamptz;
    merged_group jsonb;
    i           int;
    j           int;
    k           int;
    l           int;
BEGIN
    IF jsonb_array_length(a) > 0 AND jsonb_array_length(b) > 0 THEN
        FOR i IN 0 .. jsonb_array_length(a) - 1 LOOP
            a_group := a -> i;

            FOR j IN 0 .. jsonb_array_length(b) - 1 LOOP
                b_group := b -> j;
                merged_group := '[]'::jsonb;
                
                k := 0;
                l := 0;
                WHILE k < jsonb_array_length(a_group) AND l < jsonb_array_length(b_group) LOOP
                    a_elem  := a_group -> k;
                    a_start := (a_elem -> 'interval' ->> 0)::timestamptz;
                    a_end   := (a_elem -> 'interval' ->> 1)::timestamptz;

                    b_elem  := b_group -> l;
                    b_start := (b_elem -> 'interval' ->> 0)::timestamptz;
                    b_end   := (b_elem -> 'interval' ->> 1)::timestamptz;

                    IF a_start < b_end AND b_start < a_end THEN
                        merged_group := merged_group || jsonb_build_object(
                            'birth',   (SELECT jsonb_agg(DISTINCT v) FROM jsonb_array_elements(
                                            (a_elem -> 'birth') || (b_elem -> 'birth')
                                        ) AS v),
                            'death',    (SELECT jsonb_agg(DISTINCT v) FROM jsonb_array_elements(
                                            (a_elem -> 'death') || (b_elem -> 'death')
                                        ) AS v),
                            'interval', jsonb_build_array(
                                            GREATEST(a_start, b_start),
                                            LEAST(a_end, b_end)
                                        )
                        );
                    END IF;

                    IF a_end <= b_end THEN
                        k := k + 1;
                    ELSE
                        l := l + 1;
                    END IF;
                END LOOP;

                IF jsonb_array_length(merged_group) > 0 THEN
                    result := result || jsonb_build_array(merged_group);
                END IF;
            END LOOP;
        END LOOP;
    END IF;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;