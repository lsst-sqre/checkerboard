"""Simple app loading test for Checkerboard.
"""

import os

# These must be defined before module load currently.
os.environ["CHECKERBOARD_USER"] = "checkerboard"
os.environ["CHECKERBOARD_PW"] = "password"

from checkerboard import server

def test_app():
    app = server(start_usermapper=False)
    assert app.name == "checkerboard"
