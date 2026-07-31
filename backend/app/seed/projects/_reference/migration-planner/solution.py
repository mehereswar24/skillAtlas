def plan_migration(current: dict, target: dict) -> list[str]:
    creates: list[str] = []
    adds: list[str] = []
    alters: list[str] = []
    drops: list[str] = []
    drop_tables: list[str] = []

    for table in sorted(set(target) - set(current)):
        creates.append(f"CREATE TABLE {table}")
    for table in sorted(set(current) - set(target)):
        drop_tables.append(f"DROP TABLE {table}")

    for table in sorted(set(current) & set(target)):
        before, after = current[table], target[table]
        for column in sorted(set(after) - set(before)):
            adds.append(f"ADD COLUMN {table}.{column} {after[column]}")
        for column in sorted(set(before) & set(after)):
            if before[column] != after[column]:
                alters.append(
                    f"ALTER COLUMN {table}.{column} "
                    f"{before[column]} -> {after[column]}"
                )
        for column in sorted(set(before) - set(after)):
            drops.append(f"DROP COLUMN {table}.{column}")

    return creates + adds + alters + drops + drop_tables
