import json
import os

# Get the notebook content passed to the subtask.
# The framework will provide this as 'notebook_content_string'.
# For local testing, you might need to load this from a file or a variable.
# notebook_content_string = '''{ "cells": [ ... ] }''' # Placeholder

# In the actual subtask environment, the content is passed differently.
# The agent framework will handle providing 'INPUT_NOTEBOOK_CONTENT'.
# We assume INPUT_NOTEBOOK_CONTENT is a string variable holding the notebook's JSON data.
notebook_content_str = os.environ.get('INPUT_NOTEBOOK_CONTENT')

if notebook_content_str is None:
    print("Error: INPUT_NOTEBOOK_CONTENT environment variable not set.")
    exit(1)

try:
    data = json.loads(notebook_content_str)
except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")
    # If JSON is invalid, there's not much to do. Exit or return error.
    # For now, let's print error and return original content,
    # though in a real scenario, we might want to signal failure.
    print(notebook_content_str) # Output original content on error
    exit(1) # Signal an error

cell_modified = False
for cell in data.get('cells', []):
    if cell.get('cell_type') == 'code':
        source_lines = cell.get('source', [])
        if not isinstance(source_lines, list): # Ensure source_lines is a list
            continue

        # Check for the specific pattern: a line contains 'print(f"""'
        # and it's not closed within that cell's source lines.

        line_idx_with_pf_triple_quote = -1
        for i, line_content in enumerate(source_lines):
            if isinstance(line_content, str) and 'print(f"""' in line_content:
                line_idx_with_pf_triple_quote = i
                break # Found the start of the pattern

        if line_idx_with_pf_triple_quote != -1:
            # Pattern 'print(f"""' found. Now check if it's closed in subsequent lines OF THE SAME CELL.
            # A simple check: does any line from this point onwards, or the line itself, contain '"""'
            # that is NOT the opening one?

            opened_f_string_line = source_lines[line_idx_with_pf_triple_quote]

            # Case 1: Closed on the same line. e.g., print(f""" ... """)
            # Count occurrences of '"""'. If 2, it's opened and closed.
            # This check needs to be robust: find 'print(f"""' then look for '"""' *after* it.
            open_pattern_idx = opened_f_string_line.find('print(f"""')
            # Search for '"""' strictly after 'print(f"""'.
            if opened_f_string_line.find('"""', open_pattern_idx + len('print(f"""')) != -1:
                continue # Closed on the same line, move to next cell

            # Case 2: Check subsequent lines in the same cell for the closing '"""'
            closed_in_cell = False
            for i in range(line_idx_with_pf_triple_quote + 1, len(source_lines)):
                if isinstance(source_lines[i], str) and '"""' in source_lines[i]:
                    closed_in_cell = True
                    break

            if not closed_in_cell:
                # If we are here, 'print(f"""' was found, and no closing '"""'
                # was found on the same line (after the opening) or on subsequent lines in this cell.
                # This is the problematic cell according to the plan.

                # Check if the last line already is just '"""' or ends with '"""'
                # to prevent adding duplicate closing quotes if logic is slightly off.
                if source_lines and isinstance(source_lines[-1], str) and source_lines[-1].strip() == '"""':
                    # Already has a line with just triple quotes. Skip.
                    pass
                else:
                    source_lines.append('"""') # Add the closing triple quote as a new line
                    cell['source'] = source_lines
                    cell_modified = True
                    # As per problem, fix one cell. If multiple, this fixes the first it finds.
                    break # Exit cell loop once one is modified

# Output the modified JSON string.
# The agent framework will capture this stdout.
output_json_str = json.dumps(data, indent=2, ensure_ascii=False)
print(output_json_str)
