#!/usr/bin/env bash

coverage_badge() {
  # https://github.com/dbrgn/coverage-badge
  coverage run --branch --source=/usr/lib/python3.8/site-packages/keymapper tests/test.py
  python3 -m coverage_badge > readme/coverage.svg
  echo "coverage badge created"
}

pylint_badge() {
  # https://github.com/jongracecox/anybadge
  pylint_output=$(pylint keymapper --extension-pkg-whitelist=evdev)
  rating=$(echo $pylint_output | grep -Po "rated at .+?/" | grep -Po "\d+.\d+")
  rm data/pylint.svg
  anybadge -l pylint -v $rating -f readme/pylint.svg pylint
  echo "pylint badge created"
}

pylint_badge &
coverage_badge &

# wait for all badges to be created
wait