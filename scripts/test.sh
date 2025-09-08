#!/bin/sh
pytest --profile --nbval tests/
snakeviz prof/combined.prof