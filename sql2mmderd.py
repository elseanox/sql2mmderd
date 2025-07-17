#!/usr/bin/env python3

import re
import sys
import argparse

def clean_sql(sql_content, vendor="mysql", debug=False, debug_rows=100):
    """
    Cleans vendor-specific SQL syntax for easier parsing.
    Currently supports MySQL. Easily extensible for other vendors.
    - Removes all backticks (`)
    - Removes ENGINE, CHARSET, COLLATE, AUTO_INCREMENT lines after CREATE TABLE
    - Ensures every CREATE TABLE statement ends with a semicolon
    """
    if debug:
        print(f"[DEBUG] Entering clean_sql (vendor={vendor}, debug_rows={debug_rows})")
    if vendor == "mysql":
        # Remove all backticks
        cleaned = sql_content.replace('`', '')
        # Remove ENGINE, CHARSET, COLLATE, AUTO_INCREMENT lines after closing parenthesis
        cleaned = re.sub(r'\)\s*(ENGINE|CHARSET|COLLATE|AUTO_INCREMENT)[^;]*;', ');', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'^\s*(ENGINE|CHARSET|COLLATE|AUTO_INCREMENT)[^;]*;\s*$', '', cleaned, flags=re.MULTILINE | re.IGNORECASE)
        # Block-based approach to ensure every CREATE TABLE ends with a semicolon
        blocks = cleaned.split('CREATE TABLE')
        for i in range(1, len(blocks)):
            block = blocks[i]
            # Find the closing parenthesis that ends the CREATE TABLE definition
            closing_paren = block.rfind(')')
            if closing_paren != -1:
                after_paren = block[closing_paren:]
                # If there's no semicolon after the closing parenthesis, add it
                if not after_paren.lstrip().startswith(';'):
                    block = block[:closing_paren+1] + ';' + block[closing_paren+1:]
                blocks[i] = block
        cleaned = 'CREATE TABLE'.join(blocks)
        if debug:
            print(f"[DEBUG] First {debug_rows} lines of cleaned SQL:")
            print("\n".join(cleaned.splitlines()[:debug_rows]))
            print("[DEBUG] Exiting clean_sql")
        return cleaned
    if debug:
        print("[DEBUG] Exiting clean_sql (no vendor-specific cleaning)")
    return sql_content



def map_sql_type_to_mermaid(sql_type, debug=False):
    """
    Maps SQL data types to Mermaid-compatible types.
    """
    if debug:
        print(f"[DEBUG] map_sql_type_to_mermaid: {sql_type}")
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
    mapped = type_mapping.get(base_type, 'VARCHAR')  # Default to VARCHAR if unknown
    if debug:
        print(f"[DEBUG] map_sql_type_to_mermaid: {sql_type} -> {mapped}")
    return mapped

def parse_sql_to_mermaid_erd(sql_content, debug=False):
    """
    Parses SQL CREATE TABLE statements and generates Mermaid ERD syntax.

    Args:
        sql_content (str): The content of the SQL file containing CREATE TABLE statements.

    Returns:
        str: A string containing the Mermaid ERD syntax.
    """
    if debug:
        print("[DEBUG] Entering parse_sql_to_mermaid_erd")
        print("[DEBUG] SQL content at entry (first lines):")
        print("\n".join(sql_content.splitlines()[:20]))
        import hashlib
        print(f"[DEBUG] SQL content hash at entry: {hashlib.md5(sql_content.encode()).hexdigest()}")
    mermaid_erd_lines = ["erDiagram"]
    tables = {}
    relationships = []

    # Build parenthesis mapping for robust table extraction
    paren_locs = []
    for i, c in enumerate(sql_content):
        if c == '(' or c == ')':
            paren_locs.append((i, c))
    
    # Build parenthesis pairs
    stack = []
    paren_pairs = []
    for idx, c in paren_locs:
        if c == '(':
            stack.append(idx)
        else:  # c == ')'
            if stack:  # Check if stack is not empty
                open_idx = stack.pop()
                paren_pairs.append((open_idx, idx))
    
    if debug:
        print(f"[DEBUG] Found {len(paren_pairs)} parenthesis pairs")
    
    # Find all CREATE TABLE statements
    create_table_matches = re.finditer(r"CREATE TABLE\s+(\w+)\s*\(", sql_content, re.IGNORECASE)
    
    # Regex patterns split into simpler pieces for better maintainability
    # Piece 1: Basic column name and type
    basic_column_pattern = re.compile(r"^\s*(\w+)\s+([a-zA-Z]+(?:\(\d+(?:,\d+)?\))?)", re.IGNORECASE)
    # Piece 2: Column modifiers
    modifier_pattern = re.compile(r"(?:NOT NULL|DEFAULT\s+[^,]+|AUTO_INCREMENT)", re.IGNORECASE)
    # Piece 3: Line end
    line_end_pattern = re.compile(r",?\s*$")
    pk_pattern = re.compile(r"PRIMARY KEY\s+\(?([a-zA-Z_][a-zA-Z0-9_]*)\)?", re.IGNORECASE)
    fk_pattern = re.compile(r"FOREIGN KEY\s*\(([a-zA-Z_][a-zA-Z0-9_]*)\)\s+REFERENCES\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([a-zA-Z_][a-zA-Z0-9_]*)\)", re.IGNORECASE)

    matches = list(create_table_matches)
    if debug:
        print(f"[DEBUG] Number of CREATE TABLE matches found: {len(matches)}")
        if not matches:
            print("[WARNING] No CREATE TABLE statements found after cleaning!")
    for match_table in matches:
        table_name = match_table.group(1)
        open_paren = match_table.end() - 1  # Position of the opening parenthesis
        
        if debug:
            print(f"[DEBUG] Parsing table: {table_name}")
            print(f"[DEBUG] Opening parenthesis at position: {open_paren}")
        
        # Find the matching closing parenthesis using our mapping
        close_paren = None
        for start, end in paren_pairs:
            if start == open_paren:
                close_paren = end
                break
        
        if close_paren is None:
            if debug:
                print(f"[DEBUG] No matching closing parenthesis found for table {table_name}")
            continue
        
        # Extract the table body (everything between the parentheses)
        columns_str = sql_content[open_paren+1:close_paren]
        if debug:
            print(f"[DEBUG] Table body length for {table_name}: {len(columns_str)}")
            print(f"[DEBUG] Table body start: {columns_str[:100]}...")
        tables[table_name] = []
        # Apply simplified multi-pass approach to protect nested structures
        table_body = columns_str
        
        # Step 1: First, let's extract FOREIGN KEY constraints before any replacements
        # Look for patterns like: FOREIGN KEY (column) REFERENCES table (ref_column)
        fk_pattern = r'FOREIGN KEY\s*\(([^)]+)\)\s+REFERENCES\s+([^(]+)\s*\(([^)]+)\)'
        fk_matches = re.findall(fk_pattern, table_body, re.IGNORECASE)
        for fk_match in fk_matches:
            fk_column = fk_match[0].strip()
            ref_table = fk_match[1].strip()
            ref_column = fk_match[2].strip()
            relationships.append((table_name, fk_column, ref_table, ref_column))
            if debug:
                print(f"[DEBUG] Found foreign key: {table_name}.{fk_column} -> {ref_table}.{ref_column}")
        
        # Step 2: Remove FOREIGN KEY constraints from table body to avoid confusion
        table_body = re.sub(r'FOREIGN KEY\s*\([^)]+\)\s+REFERENCES\s+[^(]+\s*\([^)]+\),?', '', table_body, flags=re.IGNORECASE)
        
        # Step 3: Extract PRIMARY KEY constraints
        pk_pattern = r'PRIMARY KEY\s*\(([^)]+)\)'
        pk_matches = re.findall(pk_pattern, table_body, re.IGNORECASE)
        for pk_match in pk_matches:
            pk_columns = [col.strip() for col in pk_match.split(',')]
            for pk_col in pk_columns:
                if pk_col:
                    current_pk = pk_col
                    if debug:
                        print(f"[DEBUG] Found primary key: {current_pk}")
        
        # Step 4: Remove PRIMARY KEY constraints from table body
        table_body = re.sub(r'PRIMARY KEY\s*\([^)]+\),?', '', table_body, flags=re.IGNORECASE)
        
        # Step 5: Remove KEY/INDEX definitions
        table_body = re.sub(r'KEY\s+[^(]*\([^)]+\),?', '', table_body, re.IGNORECASE)
        
        # Step 6: Remove CONSTRAINT definitions
        table_body = re.sub(r'CONSTRAINT\s+[^,]+', '', table_body, re.IGNORECASE)
        
        if debug:
            print(f"[DEBUG] Table body after replacements for {table_name}:")
            print(f"[DEBUG] {table_body[:200]}...")
        
        # Step 7: Now safe to split by comma (constraints have been removed)
        comma_separated = [defn.strip() for defn in table_body.split(',') if defn.strip()]
        if debug:
            print(f"[DEBUG] Comma-separated parts for {table_name}:")
            for i, part in enumerate(comma_separated, 1):
                print(f"[DEBUG]   {i}. {part[:60]}...")
        
        # Step 8: Process each part - now only column definitions should remain
        column_definitions = []
        for definition in comma_separated:
            # Check if this looks like a column definition (has a data type)
            if any(data_type in definition.lower() for data_type in ['varchar', 'char', 'int', 'datetime', 'longtext', 'bit', 'decimal', 'float', 'double', 'date', 'time', 'timestamp', 'year', 'boolean', 'blob', 'json', 'enum', 'set', 'text']):
                column_definitions.append(definition)
                if debug:
                    print(f"[DEBUG] Found column: {definition}")
            else:
                if debug:
                    print(f"[DEBUG] Skipping non-column definition: {definition[:50]}...")
        # Process column definitions using the simplified approach
        current_columns = []
        current_pk = None
        
        for definition in column_definitions:
            # Extract column name and type from the definition
            # Format: column_name data_type(size) modifiers
            parts = definition.split()
            if len(parts) >= 2:
                col_name = parts[0]
                raw_type = parts[1].split('(')[0]  # Remove size specification
                col_type = map_sql_type_to_mermaid(raw_type, debug=debug)
                current_columns.append((col_name, col_type))
                if debug:
                    print(f"[DEBUG] Added column: {col_name} {col_type}")

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
    if debug:
        print("[DEBUG] Exiting parse_sql_to_mermaid_erd")
    return "\n".join(mermaid_erd_lines)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert SQL CREATE TABLE statements to Mermaid ERD.")
    parser.add_argument("input_sql_file", help="Input SQL file path")
    parser.add_argument("output_mermaid_file", nargs="?", help="Output Mermaid file path (optional)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--debug-rows", type=int, default=100, help="Number of lines to show in debug output (default: 100)")
    args = parser.parse_args()

    input_file_path = args.input_sql_file
    output_file_path = args.output_mermaid_file
    debug = args.debug
    debug_rows = args.debug_rows

    if debug:
        print(f"[DEBUG] Arguments: input_file_path={input_file_path}, output_file_path={output_file_path}, debug={debug}, debug_rows={debug_rows}")

    try:
        with open(input_file_path, 'r') as f:
            sql_content = f.read()
        if debug:
            print("[DEBUG] Read input SQL file")
        sql_content = clean_sql(sql_content, vendor="mysql", debug=debug, debug_rows=debug_rows)
        if debug:
            print("[DEBUG] Cleaned SQL content (before parse_sql_to_mermaid_erd):")
            print("\n".join(sql_content.splitlines()[:debug_rows]))
            import hashlib
            print(f"[DEBUG] Cleaned SQL hash: {hashlib.md5(sql_content.encode()).hexdigest()}")
        mermaid_output = parse_sql_to_mermaid_erd(sql_content, debug=debug)
        if debug:
            print("[DEBUG] Parsed Mermaid ERD")
        if output_file_path:
            with open(output_file_path, 'w') as f:
                f.write("```mermaid\n")
                f.write(mermaid_output)
                f.write("\n```\n")
            print(f"Mermaid ERD saved to: {output_file_path}")
        else:
            print(mermaid_output)

    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_file_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
