#!/usr/bin/env bash

# pip install git+https://github.com/jongracecox/anybadge

coverage_badge() {
  python3 -m coverage erase
  python3 -m coverage run -m unittest discover -s ./tests/
  python3 -m coverage combine
  rating=$(python3 -m coverage report | tail -n 1 | ack "\d+%" -o | ack "\d+" -o)
  echo "coverage rating: $rating"
  rm readme/coverage.svg
  python3 -m anybadge -l coverage -v $rating -f readme/coverage.svg coverage

  python3 -m coverage report -m
  echo "coverage badge created"
}

pylint_badge() {
  pylint_output=$(python3 -m pylint inputremapper --extension-pkg-whitelist=evdev)
  rating=$(echo $pylint_output | grep -Po "rated at .+?/" | grep -Po "\d+.\d+")
  rm readme/pylint.svg
  python3 -m anybadge -l pylint -v $rating -f readme/pylint.svg pylint

  echo "pylint rating: $rating"
  echo "pylint badge created"
}

pylint_badge &
coverage_badge &

# wait for all badges to be created
wait
