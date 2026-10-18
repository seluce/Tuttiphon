"""Automated tests for the Python part (app/). Run from the project folder:

    python3 -m unittest discover -s tests/python -t .      (or: npm run test:py)

Every test file first imports `from tests.python import env` – this sets a fresh temp folder as the
data folder and Navidrome folder before app.* is loaded. The tests need neither network nor NAS.
"""
