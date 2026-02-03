"""
Migration script for OEE (Overall Equipment Effectiveness) tables
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'warehouse.db')

if not os.path.exists(db_path):
    print(f"Database not found at: {db_path}")
    exit(1)

print(f"Connecting to: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create OEE tables
tables = [
    # Shift Logs - daily OEE tracking per machine
    """
    CREATE TABLE IF NOT EXISTS shift_logs (
        id INTEGER PRIMARY KEY,
        machine_id INTEGER NOT NULL REFERENCES machines(id),
        shift_date DATE NOT NULL,
        shift VARCHAR(20) DEFAULT 'day',

        planned_production_minutes FLOAT DEFAULT 480,

        breakdown_minutes FLOAT DEFAULT 0,
        setup_changeover_minutes FLOAT DEFAULT 0,
        material_shortage_minutes FLOAT DEFAULT 0,
        other_downtime_minutes FLOAT DEFAULT 0,
        downtime_notes TEXT,

        ideal_cycle_time_seconds FLOAT,
        actual_cycles INTEGER DEFAULT 0,
        parts_per_cycle INTEGER DEFAULT 1,

        total_parts_produced INTEGER DEFAULT 0,
        good_parts INTEGER DEFAULT 0,
        scrap_parts INTEGER DEFAULT 0,
        rework_parts INTEGER DEFAULT 0,

        scrap_startup INTEGER DEFAULT 0,
        scrap_colour INTEGER DEFAULT 0,
        scrap_short_shot INTEGER DEFAULT 0,
        scrap_flash INTEGER DEFAULT 0,
        scrap_sink_marks INTEGER DEFAULT 0,
        scrap_warp INTEGER DEFAULT 0,
        scrap_other INTEGER DEFAULT 0,
        scrap_notes TEXT,

        production_order_id INTEGER REFERENCES production_orders(id),
        operator_name VARCHAR(100),

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # Downtime Reasons - standardized codes
    """
    CREATE TABLE IF NOT EXISTS downtime_reasons (
        id INTEGER PRIMARY KEY,
        code VARCHAR(20) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        category VARCHAR(50),
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # Downtime Events - individual occurrences
    """
    CREATE TABLE IF NOT EXISTS downtime_events (
        id INTEGER PRIMARY KEY,
        machine_id INTEGER NOT NULL REFERENCES machines(id),
        shift_log_id INTEGER REFERENCES shift_logs(id),
        reason_id INTEGER REFERENCES downtime_reasons(id),

        start_time DATETIME NOT NULL,
        end_time DATETIME,
        duration_minutes FLOAT,

        notes TEXT,
        reported_by VARCHAR(100),

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # Scrap Reasons - standardized codes
    """
    CREATE TABLE IF NOT EXISTS scrap_reasons (
        id INTEGER PRIMARY KEY,
        code VARCHAR(20) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        category VARCHAR(50),
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # Scrap Events - individual occurrences
    """
    CREATE TABLE IF NOT EXISTS scrap_events (
        id INTEGER PRIMARY KEY,
        machine_id INTEGER NOT NULL REFERENCES machines(id),
        production_order_id INTEGER REFERENCES production_orders(id),
        shift_log_id INTEGER REFERENCES shift_logs(id),
        reason_id INTEGER REFERENCES scrap_reasons(id),

        quantity INTEGER NOT NULL,
        weight_kg FLOAT,
        estimated_cost FLOAT,

        occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        notes TEXT,
        reported_by VARCHAR(100),

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
]

# Create tables
for sql in tables:
    try:
        cursor.execute(sql)
        table_name = sql.split('CREATE TABLE IF NOT EXISTS')[1].split('(')[0].strip()
        print(f"  [OK] Created/verified table: {table_name}")
    except Exception as e:
        print(f"  [ERROR] {e}")

# Create indexes
indexes = [
    "CREATE INDEX IF NOT EXISTS idx_shift_logs_machine_date ON shift_logs(machine_id, shift_date)",
    "CREATE INDEX IF NOT EXISTS idx_shift_logs_date ON shift_logs(shift_date)",
    "CREATE INDEX IF NOT EXISTS idx_downtime_events_machine ON downtime_events(machine_id)",
    "CREATE INDEX IF NOT EXISTS idx_scrap_events_machine ON scrap_events(machine_id)",
    "CREATE INDEX IF NOT EXISTS idx_scrap_events_po ON scrap_events(production_order_id)",
]

print("\nCreating indexes...")
for sql in indexes:
    try:
        cursor.execute(sql)
        print(f"  [OK] {sql.split('idx_')[1].split(' ')[0]}")
    except Exception as e:
        print(f"  [ERROR] {e}")

# Insert default downtime reasons
default_downtime_reasons = [
    ('BD', 'Machine Breakdown', 'unplanned'),
    ('SC', 'Setup/Changeover', 'planned'),
    ('MS', 'Material Shortage', 'unplanned'),
    ('TF', 'Tool/Mould Failure', 'unplanned'),
    ('PM', 'Planned Maintenance', 'planned'),
    ('NO', 'No Operator', 'unplanned'),
    ('QI', 'Quality Issue', 'quality'),
    ('OT', 'Other', 'unplanned'),
]

print("\nInserting default downtime reasons...")
for code, name, category in default_downtime_reasons:
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO downtime_reasons (code, name, category) VALUES (?, ?, ?)",
            (code, name, category)
        )
        print(f"  [OK] {code}: {name}")
    except Exception as e:
        print(f"  [ERROR] {code}: {e}")

# Insert default scrap reasons
default_scrap_reasons = [
    ('ST', 'Startup Scrap', 'process'),
    ('SS', 'Short Shot', 'process'),
    ('FL', 'Flash', 'process'),
    ('SK', 'Sink Marks', 'process'),
    ('WP', 'Warpage', 'process'),
    ('BM', 'Burn Marks', 'process'),
    ('CL', 'Colour Issue', 'material'),
    ('CT', 'Contamination', 'material'),
    ('DM', 'Damage/Handling', 'operator'),
    ('TW', 'Tool Wear', 'tooling'),
    ('OT', 'Other', 'other'),
]

print("\nInserting default scrap reasons...")
for code, name, category in default_scrap_reasons:
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO scrap_reasons (code, name, category) VALUES (?, ?, ?)",
            (code, name, category)
        )
        print(f"  [OK] {code}: {name}")
    except Exception as e:
        print(f"  [ERROR] {code}: {e}")

conn.commit()
conn.close()
print("\nOEE tables migration complete!")
