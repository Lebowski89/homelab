## Useful commands for Spilo

### Find primary cluster node and check connectivity

```
curl -s -i http://127.0.0.1:8008/leader  | head -n 1
curl -s -i http://127.0.0.1:8008/primary | head -n 1
curl -s http://127.0.0.1:8008/ | head
```

### Restore a database dump:

```
docker cp /opt/spilo/dumps/<database>.dump spilo:/tmp/<database>.dump

docker exec -i spilo pg_restore \
  -U postgres \
  --no-owner \
  --no-privileges \
  -C -d postgres \
  /tmp/<database>.dump
```

### Alter database owner and grant privileges:

```
docker exec -it spilo psql -U postgres -d postgres -c \
  "ALTER DATABASE \"<database>\" OWNER TO <user>;"
```

```
DB="<database>"

sudo docker exec -i spilo psql -U postgres -d "${DB}" -v ON_ERROR_STOP=1 <<'SQL'
-- Make sure public schema is owned by the app role (common gotcha)
ALTER SCHEMA public OWNER TO <user>;

-- If your app uses public schema objects, grant what it needs
GRANT ALL ON SCHEMA public TO <user>;

-- Make existing objects accessible
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO <user>;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO <user>;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO <user>;

-- Ensure future objects created by migrations are usable
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON TABLES TO <user>;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON SEQUENCES TO <user>;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON FUNCTIONS TO <user>;
SQL
```

```
DB="<database>"

sudo docker exec -i spilo psql -U postgres -d "${DB}" -v ON_ERROR_STOP=1 <<'SQL'
DO $$
DECLARE r record;
BEGIN
  -- tables
  FOR r IN
    SELECT schemaname, tablename
    FROM pg_tables
    WHERE schemaname NOT IN ('pg_catalog','information_schema')
  LOOP
    EXECUTE format('ALTER TABLE %I.%I OWNER TO <user>;', r.schemaname, r.tablename);
  END LOOP;

  -- sequences
  FOR r IN
    SELECT sequence_schema, sequence_name
    FROM information_schema.sequences
    WHERE sequence_schema NOT IN ('pg_catalog','information_schema')
  LOOP
    EXECUTE format('ALTER SEQUENCE %I.%I OWNER TO <user>;', r.sequence_schema, r.sequence_name);
  END LOOP;

  -- views
  FOR r IN
    SELECT table_schema, table_name
    FROM information_schema.views
    WHERE table_schema NOT IN ('pg_catalog','information_schema')
  LOOP
    EXECUTE format('ALTER VIEW %I.%I OWNER TO <user>;', r.table_schema, r.table_name);
  END LOOP;
END $$;
SQL
```
