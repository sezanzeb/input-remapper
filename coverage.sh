#!/usr/bin/env bash
# https://github.com/dbrgn/coverage-badge
coverage run --branch --source=/usr/lib/python3.8/site-packages/keymapper tests/test.py
python3 -m coverage_badge > data/coverage.svg
