#!/usr/bin/env bash

coverage_badge() {
  # https://github.com/dbrgn/coverage-badge
  coverage run tests/test.py
  python3 -m coverage_badge > readme/coverage.svg
  coverage combine
  coverage report -m
  echo "coverage badge created"
}

pylint_badge() {
  # https://github.com/jongracecox/anybadge
  pylint_output=$(pylint keymapper --extension-pkg-whitelist=evdev)
  rating=$(echo $pylint_output | grep -Po "rated at .+?/" | grep -Po "\d+.\d+")
  rm readme/pylint.svg
  anybadge -l pylint -v $rating -f readme/pylint.svg pylint
  echo $rating
  echo "pylint badge created"
}

pylint_badge &
coverage_badge &

# wait for all badges to be created
wait
