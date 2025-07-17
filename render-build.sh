#!/usr/bin/env bash
pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH=0 playwright install
