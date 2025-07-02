#!/usr/bin/env python3

import re
import sys

def map_sql_type_to_mermaid(sql_type):
    """
    Maps SQL data types to Mermaid-compatible types.
    """
    sql_type = sql_type.upper()
    
    # Basic type mappings - using only Mermaid ERD compatible types
    type_mapping = {
        'VARCHAR': 'VARCHAR',
        'CHAR': 'CHAR',
        'TEXT': 'VARCHAR',
        'LONGTEXT': 'VARCHAR',
        'MEDIUMTEXT': 'VARCHAR',
        'TINYTEXT': 'VARCHAR',
        'INT': 'INT',
        'INTEGER': 'INT',
        'BIGINT': 'INT',
        'SMALLINT': 'INT',
        'TINYINT': 'INT',
        'DECIMAL': 'DECIMAL',
        'FLOAT': 'FLOAT',
        'DOUBLE': 'FLOAT',
        'DATETIME': 'DATETIME',
        'TIMESTAMP': 'DATETIME',
        'DATE': 'DATE',
        'TIME': 'TIME',
        'YEAR': 'INT',
        'BIT': 'BOOLEAN',
        'BOOLEAN': 'BOOLEAN',
        'BLOB': 'VARCHAR',
        'LONGBLOB': 'VARCHAR',
        'MEDIUMBLOB': 'VARCHAR',
        'TINYBLOB': 'VARCHAR',
        'JSON': 'VARCHAR',
        'ENUM': 'VARCHAR',
        'SET': 'VARCHAR'
    }
    
    # Extract base type (remove size specifications)
    base_type = sql_type.split('(')[0] if '(' in sql_type else sql_type
    
    return type_mapping.get(base_type, 'VARCHAR')  # Default to VARCHAR if unknown

def parse_sql_to_mermaid_erd(sql_content):
    """
    Parses SQL CREATE TABLE statements and generates Mermaid ERD syntax.

    Args:
        sql_content (str): The content of the SQL file containing CREATE TABLE statements.

    Returns:
        str: A string containing the Mermaid ERD syntax.
    """
    mermaid_erd_lines = ["erDiagram"]
    tables = {}
    relationships = []

    # Regex to find CREATE TABLE statements and capture table name
    table_pattern = re.compile(r"CREATE TABLE\s+`?(\w+)`?\s*\((.*?)\);", re.IGNORECASE | re.DOTALL)
    
    # Regex to find column definitions, primary keys, and foreign keys within a table
    column_pattern = re.compile(r"^\s*`?(\w+)`?\s+([a-zA-Z]+(?:\(\d+(?:,\d+)?\))?)(?:\s+NOT NULL)?(?:(?:\s+DEFAULT\s+[\w\d\.'-]+)?(?:\s+AUTO_INCREMENT)?)?,?\s*$", re.IGNORECASE)
    pk_pattern = re.compile(r"PRIMARY KEY\s+\(?`?(\w+)`?\)?", re.IGNORECASE)
    fk_pattern = re.compile(r"FOREIGN KEY\s*\([`\"]?([a-zA-Z_][a-zA-Z0-9_]*)[`\"]?\)\s+REFERENCES\s+[`\"]?([a-zA-Z_][a-zA-Z0-9_]*)[`\"]?\s*\([`\"]?([a-zA-Z_][a-zA-Z0-9_]*)[`\"]?\)", re.IGNORECASE)

    for match_table in table_pattern.finditer(sql_content):
        table_name = match_table.group(1)
        columns_str = match_table.group(2)
        
        tables[table_name] = []
        
        # Split columns_str by lines, handling commas and potential multi-line definitions
        column_definitions = [line.strip() for line in columns_str.split('\n') if line.strip()]

        current_columns = []
        current_pk = None

        for line in column_definitions:
            # Skip lines that are just comments or empty after stripping
            if not line or line.startswith('--') or line.startswith('/*!'):
                continue

            # Check for PRIMARY KEY
            match_pk = pk_pattern.search(line)
            if match_pk:
                current_pk = match_pk.group(1)
                continue # PK line doesn't define a column directly for ERD

            # Check for FOREIGN KEY
            match_fk = fk_pattern.search(line)
            if match_fk:
                fk_column = match_fk.group(1)
                ref_table = match_fk.group(2)
                ref_column = match_fk.group(3)
                # Store relationship: (from_table, from_col, to_table, to_col)
                relationships.append((table_name, fk_column, ref_table, ref_column))
                continue # FK line doesn't define a column directly for ERD

            # Check for regular column
            match_column = column_pattern.match(line)
            if match_column:
                col_name = match_column.group(1)
                raw_type = match_column.group(2).split(' ')[0].rstrip(',') # Get base type and remove trailing comma
                col_type = map_sql_type_to_mermaid(raw_type)  # Map to Mermaid-compatible type
                current_columns.append((col_name, col_type))

        # Add columns to the table structure
        for col_name, col_type in current_columns:
            # Check if this column is also a foreign key
            is_fk = any(r[0] == table_name and r[1] == col_name for r in relationships)
            is_pk = col_name == current_pk
            
            if is_fk:
                # If it's a foreign key, include the data type
                tables[table_name].append(f"{col_name} {col_type} FK")
            else:
                # Regular column with data type
                pk_suffix = " PK" if is_pk else ""
                tables[table_name].append(f"{col_name} {col_type}{pk_suffix}")

    # Generate Mermaid ERD table definitions
    for table_name, cols in tables.items():
        mermaid_erd_lines.append(f"{table_name} {{")
        mermaid_erd_lines.extend(cols)
        mermaid_erd_lines.append("}")

    # Generate Mermaid ERD relationships
    for from_table, from_col, to_table, to_col in relationships:
        # Mermaid ERD syntax for relationships:
        # TABLE1 ||--|{ TABLE2 : relationship_description
        # ||--|{ means one-to-many (one parent, many children)
        # ||--o{ means one-to-zero-or-many
        # |o--o| means zero-or-one-to-zero-or-one
        # Let's use ||--o{ as a common default for FKs
        mermaid_erd_lines.append(f"{from_table} ||--o{{ {to_table} : \"FK to {to_col}\"")

    return "\n".join(mermaid_erd_lines)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sql2er.py <input_sql_file> [output_mermaid_file]")
        sys.exit(1)

    input_file_path = sys.argv[1]
    output_file_path = None
    if len(sys.argv) > 2:
        output_file_path = sys.argv[2]

    try:
        with open(input_file_path, 'r') as f:
            sql_content = f.read()

        mermaid_output = parse_sql_to_mermaid_erd(sql_content)

        if output_file_path:
            with open(output_file_path, 'w') as f:
                f.write("```mermaid\n")
                f.write(mermaid_output)
                f.write("\n```\n")
            print(f"Mermaid ERD saved to: {output_file_path}")
        else:
            print("\n--- Generated Mermaid ERD ---\n")
            print(mermaid_output)
            print("\n---------------------------\n")

    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_file_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
