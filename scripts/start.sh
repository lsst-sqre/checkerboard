#!/bin/bash
#
# Start the Checkerboard application inside the Docker image.
#

set -eu

cmd="uvicorn --factory checkerboard.main:create_app --host 0.0.0.0 --port 8080"

exec ${cmd}
