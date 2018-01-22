#!/usr/bin/env python
"""ghslacker microservice framework.
"""
# Python 2/3 compatibility
try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError
from apikit import APIFlask
from apikit import BackendError
from flask import jsonify

log = None


def server(run_standalone=False):
    """Create the app and then run it.
    """
    # Add "/ghslacker" for mapping behind api.lsst.codes
    app = APIFlask(name="uservice-ghslacker",
                   version="0.0.1",
                   repository="https://github.com/sqre-lsst/uservice-ghslacker",
                   description="Slack <-> GitHub user mapper",
                   route=["/", "/ghslacker"],
                   auth={"type": "bitly-proxy",
                         "data": {"username": "",
                                   "password": "",
                                   "endpoint": "https://FIXME-BACKEND-URL/oauth2/start" }})
    app.config["SESSION"] = None
    global log
    # Gross, but efficacious
    log = app.config["LOGGER"]

    @app.errorhandler(BackendError)
    # pylint can't understand decorators.
    # pylint: disable=unused-variable
    def handle_invalid_usage(error):
        """Custom error handler.
        """
        errdict = error.to_dict()
        log.error(errdict)
        response = jsonify(errdict)
        response.status_code = error.status_code
        return response

    @app.route("/")
    def healthcheck():
        """Default route to keep Ingress controller happy.
        """
        return "OK"

    @app.route("/ghslacker")
    @app.route("/ghslacker/")
    # @app.route("/ghslacker/<parameter>")
    # or, if you have a parameter, def route_function(parameter=None):
    def route_function():
        """Slack <-> GitHub user mapper
        """
        # FIXME: service logic goes here
        # See https://sqr-015.lsst.io for details.
        # - store HTTP session in app.config["SESSION"]
        # - raise errors as BackendError
        # - return your results with jsonify
        # - set status_code on the response as needed
        return

    if run_standalone:
        app.run(host='0.0.0.0', threaded=True)
    # Otherwise, we're running under uwsgi, and it wants the app.
    return app


def standalone():
    """Entry point for running as its own executable.
    """
    server(run_standalone=True)


if __name__ == "__main__":
    standalone()
