#!/usr/bin/env bash

# sudo pip install git+https://github.com/jongracecox/anybadge

coverage_badge() {
  coverage run tests/test.py
  coverage combine
  rating=$(coverage report | tail -n 1 | ack "\d+%" -o | ack "\d+" -o)
  echo "coverage rating: $rating"
  rm readme/coverage.svg
  anybadge -l coverage -v $rating -f readme/coverage.svg coverage

  coverage report -m
  echo "coverage badge created"
}

pylint_badge() {
  pylint_output=$(pylint inputremapper --extension-pkg-whitelist=evdev)
  rating=$(echo $pylint_output | grep -Po "rated at .+?/" | grep -Po "\d+.\d+")
  rm readme/pylint.svg
  anybadge -l pylint -v $rating -f readme/pylint.svg pylint

  echo "pylint rating: $rating"
  echo "pylint badge created"
}

pylint_badge &
coverage_badge &

# wait for all badges to be created
wait
