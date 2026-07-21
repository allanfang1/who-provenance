# Who Provenance

Who Provenance is a small demo for SQL provenance and query rewriting. It includes a command-line workflow for running database experiments and a Streamlit app for interactive exploration.

## Project Structure

```text
README.md
requirements.txt
proof/
	proof.md
	proof.tex
src/
	db.py
	demo_db.py
	demo.py
	main.py
	ast_rewriter.py
	cte_rewriter.py
streamlit_app/
	app.py
	db_client.py
	action_dialogs.py
	helper.py
```

## Installation

1. Create and activate a virtual environment.
2. Install the dependencies:

```bash
pip install -r requirements.txt
```

## CLI Usage

The CLI entry points live under `src/`.

Run the legacy provenance harness:

```bash
python src/main.py reset
python src/main.py check
python src/main.py test_seeding
python src/main.py test_classic
python src/main.py test_annotate
python src/main.py test_join
python src/main.py test_ast
```

Run the demo harness:

```bash
python src/demo.py reset
python src/demo.py setup
python src/demo.py check
python src/demo.py classic
python src/demo.py pos_neg
python src/demo.py pos_neg_blame
python src/demo.py full_provenance
```

## Streamlit Usage

Start the interactive app from the repository root:

```bash
python -m streamlit run streamlit_app/app.py
```

The app opens with a database page for managing demo data and a query page for running SQL and inspecting provenance-aware results.
