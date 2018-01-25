#!/usr/bin/env python
"""ghslacker microservice framework.
"""
# Python 2/3 compatibility
import os
import sched
import time
try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError
from apikit import APIFlask, BackendError
from flask import jsonify, request
from threading import Thread
from usermapper import Usermapper

log = None
USER = os.environ["GHSLACKER_USER"]
PW = os.environ["GHSLACKER_PW"]
FIELD = os.environ.get("GHSLACKER_FIELD") or "GitHub Username"
SCHED = sched.scheduler(time.time, time.sleep)
CACHE_LIFETIME = 3600  # seconds


def server(run_standalone=False):
    """Create the app and then run it.
    """
    # Add "/ghslacker" for mapping behind api.lsst.codes
    app = APIFlask(name="uservice-ghslacker",
                   version="0.0.1",
                   repository="https://github.com/sqre-lsst/uservice-ghslacker",
                   description="Slack <-> GitHub user mapper",
                   route=["/", "/ghslacker"],
                   auth={"type": "basic",
                         "data": {"username": USER,
                                  "password": PW
                                  }
                         }
                   )
    app.config["MAPPER"] = None
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
    @app.route("/ghslacker/usermap")
    # @app.route("/ghslacker/<parameter>")
    # or, if you have a parameter, def route_function(parameter=None):
    def get_usermap():
        """Slack <-> GitHub user mapper.  Returns entire user map as JSON.
        """
        # FIXME: service logic goes here
        # See https://sqr-015.lsst.io for details.
        # - raise errors as BackendError
        # - return your results with jsonify
        # - set status_code on the response as needed
        _precheck()
        return jsonify(app.config["MAPPER"].usermap)

    @app.route("/ghslacker/<slack_user>")
    @app.route("/ghslacker/<slack_user>/")
    @app.route("/ghslacker/slack/<slack_user>")
    @app.route("/ghslacker/slack/<slack_user>/")
    def get_github_user(slack_user=None):
        """Returns JSON object mapping Slack user to GitHub user, given
        Slack user."""
        _precheck()
        if slack_user:
            gh_user = app.config["MAPPER"].github_for_slack_user(slack_user)
            if gh_user:
                return jsonify({slack_user: gh_user})
            raise BackendError(reason="Not Found", status_code=404,
                               content=("No GitHub user for Slack user %s" %
                                        slack_user))
        else:
            slack_user = "<none>"
        raise BackendError(reason="Not Found", status_code=404,
                           content="Slack User %s not found" % slack_user)

    @app.route("/ghslacker/github/<github_user>")
    @app.route("/ghslacker/github/<github_user>/")
    def get_slack_user(github_user=None):
        """Returns JSON object mapping Slack user to GitHub user, given
        GitHub user."""
        _precheck()
        if github_user:
            sl_user = app.config["MAPPER"].slack_for_github_user(github_user)
            if sl_user:
                return jsonify({sl_user: github_user})
            raise BackendError(reason="Not Found", status_code=404,
                               content=("No Slack user for GitHub user %s" %
                                        github_user))
        else:
            github_user = "<none>"
        raise BackendError(reason="Not Found", status_code=404,
                           content="GitHub User %s not found" % github_user)

    def _precheck():
        _auth()
        app.config["MAPPER"].wait_for_initialization()

    def _auth():
        if request.authorization is None:
            raise BackendError(reason="Unauthorized", status_code=401,
                               content="No authorization provided.")
        inboundauth = request.authorization
        if (inboundauth.username != USER or inboundauth.password != PW):
            raise BackendError(reason="Unauthorized", status_code=401,
                               content="Incorrect authorization.")
        if not app.config["MAPPER"]:
            _set_mapper()

    def _set_mapper():
        mapper = Usermapper(bot_token=os.environ["SLACK_BOT_TOKEN"],
                            app_token=os.environ["SLACK_APP_TOKEN"],
                            field_name=FIELD)
        if not mapper:
            raise BackendError(reason="Internal Server Error",
                               content="Failed to get mapper object.",
                               status_code=500)
        app.config["MAPPER"] = mapper
        SCHED.enter(CACHE_LIFETIME, 1, mapper.rebuild_usermap, ())
        Thread(target=SCHED.run, name='mapbuilder').start()

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
