-- soft delete
CREATE OR REPLACE TRIGGER {trigger_name}
BEFORE DELETE ON {table_name}
FOR EACH ROW
EXECUTE FUNCTION soft_delete();

