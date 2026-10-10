#!/usr/bin/env bash
# Double-click to start the IRIS workspace. Keep this window open; close it to stop.
cd "$(dirname "$0")"
( sleep 6; open "http://localhost:8000/" ) &
bash run_web.sh
