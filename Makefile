.PHONY: validate demo

validate:
	python3 scripts/validate_repo.py

# One-command end-to-end demo: receiver + signed event + inbox row.
# See docs/quickstart.md for details.
demo:
	bash scripts/demo.sh

