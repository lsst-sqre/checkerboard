"""Simple app loading test for Checkerboard.
"""

import os


def test_app() -> None:
    # The environment variables must be defined before the module is imported.
    os.environ["CHECKERBOARD_USER"] = "checkerboard"
    os.environ["CHECKERBOARD_PW"] = "password"
    from checkerboard import server

    app = server(start_usermapper=False)
    assert app.name == "checkerboard"
