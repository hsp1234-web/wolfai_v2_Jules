import json
import ast
import sys

notebook_path = "run_in_colab_v5.ipynb"

try:
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook_content_str = f.read()

    notebook_json = json.loads(notebook_content_str)

    if not notebook_json.get("cells"):
        print("ERROR: No cells found in the notebook.")
        sys.exit(1)

    code_cells_source = []
    for cell in notebook_json["cells"]:
        if cell.get("cell_type") == "code":
            if cell.get("source"):
                # Source can be a list of strings or a single string.
                source_content = cell["source"]
                if isinstance(source_content, list):
                    code_cells_source.append("".join(source_content))
                elif isinstance(source_content, str):
                    code_cells_source.append(source_content)

    if not code_cells_source:
        print("ERROR: No code found in any code cells.")
        sys.exit(1)

    # For this notebook, we expect one major code cell.
    # We'll check the syntax of the first one found.
    python_code = code_cells_source[0]

    # Remove Colab specific magic commands if they are at the start of lines,
    # as ast.parse won't understand them.
    # Common ones: #@param, #@title, !cmd, %cmd
    # A simple approach for this script: filter lines starting with known patterns.
    # This is not exhaustive for all magics but covers common cases in this notebook.
    lines = python_code.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped_line = line.lstrip()
        if stripped_line.startswith(("#@title", "#@markdown", "#@param")):
            cleaned_lines.append("") # Keep line numbers somewhat consistent by adding empty line
        elif stripped_line.startswith(("%", "!")):
             cleaned_lines.append("") # Or just pass if we don't want to execute shell/magic
        else:
            cleaned_lines.append(line)

    cleaned_python_code = "\n".join(cleaned_lines)

    ast.parse(cleaned_python_code)
    print("Syntax OK")

except FileNotFoundError:
    print(f"ERROR: Notebook file '{notebook_path}' not found.")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"ERROR: Could not decode JSON from '{notebook_path}'. Error: {e}")
    sys.exit(1)
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
    # Additional details for debugging:
    print(f"Error class: {e.__class__.__name__}")
    print(f"Error message: {e.msg}")
    print(f"Line number: {e.lineno}")
    print(f"Offset: {e.offset}")
    if e.text:
        print(f"Problematic line: {e.text.strip()}")
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    sys.exit(1)
