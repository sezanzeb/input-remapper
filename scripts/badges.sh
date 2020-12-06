#!/usr/bin/env bash

# sudo pip install git+https://github.com/jongracecox/anybadge
# sudo pip install git+https://github.com/dbrgn/coverage-badge

coverage_badge() {
  coverage run tests/test.py
  coverage combine
  python3 -m coverage_badge > readme/coverage.svg
  coverage report -m
  echo "coverage badge created"
}

pylint_badge() {
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
