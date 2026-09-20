-- insert audit
CREATE OR REPLACE TRIGGER {trigger_name}
AFTER INSERT ON {table_name}
FOR EACH ROW
EXECUTE FUNCTION insert_audit();