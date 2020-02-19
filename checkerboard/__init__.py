#!/usr/bin/env python
"""SQuaRE Checkerboard microservice (api.lsst.codes-compliant).
"""
from .server import server, standalone
__all__ = ["server", "standalone"]
