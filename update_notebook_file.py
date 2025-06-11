import os

# The updated notebook content is expected to be in the INPUT_NOTEBOOK_CONTENT variable.
# This variable should have been populated by the output of the previous subtask.
new_content = os.environ.get('INPUT_NOTEBOOK_CONTENT')
file_path = "run_in_colab_v5.ipynb"

if new_content is None:
    print("Error: INPUT_NOTEBOOK_CONTENT environment variable not set.")
    exit(1) # Signal an error

try:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Successfully wrote updated content to {file_path}")
except Exception as e:
    print(f"Error writing to file {file_path}: {e}")
    exit(1) # Signal an error
