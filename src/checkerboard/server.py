#!/usr/bin/env python
"""Checkerboard microservice framework.
"""
# Python 2/3 compatibility
import os
import sched
import time
from threading import Thread

from apikit import APIFlask, BackendError
from flask import jsonify, request

from .usermapper import Usermapper

try:
    from json.decoder import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

log = None
USER = os.environ["CHECKERBOARD_USER"]
PW = os.environ["CHECKERBOARD_PW"]
FIELD = os.environ.get("CHECKERBOARD_FIELD") or "GitHub Username"
SCHED = sched.scheduler(time.time, time.sleep)
CACHE_LIFETIME = int(os.environ.get("CHECKERBOARD_CACHE_LIFETIME") or 3600)


def server(run_standalone=False, start_usermapper=True):
    """Create the app and then run it.
    """
    # Add "/checkerboard" for mapping behind api.lsst.codes
    app = APIFlask(
        name="checkerboard",
        version="0.2.0",
        repository="https://github.com/sqre-lsst/checkerboard",
        description="Slack <-> GitHub user mapper",
        route=["/", "/checkerboard"],
        auth={"type": "basic", "data": {"username": USER, "password": PW}},
    )

    # Add our internal functions.

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

    @app.route("/checkerboard")
    @app.route("/checkerboard/")
    @app.route("/checkerboard/usermap")
    # @app.route("/checkerboard/<parameter>")
    # or, if you have a parameter, def route_function(parameter=None):
    def get_usermap():
        """Slack <-> GitHub user mapper.  Returns entire user map as JSON.
        """
        _precheck()
        return jsonify(app.config["MAPPER"].usermap)

    @app.route("/checkerboard/<slack_user>")
    @app.route("/checkerboard/<slack_user>/")
    @app.route("/checkerboard/slack/<slack_user>")
    @app.route("/checkerboard/slack/<slack_user>/")
    def get_github_user(slack_user=None):
        """Returns JSON object mapping Slack user to GitHub user, given
        Slack user."""
        _precheck()
        if slack_user:
            gh_user = app.config["MAPPER"].github_for_slack_user(slack_user)
            if gh_user:
                return jsonify({slack_user: gh_user})
            raise BackendError(
                reason="Not Found",
                status_code=404,
                content=("No GitHub user for Slack user %s" % slack_user),
            )
        else:
            slack_user = "<none>"
        raise BackendError(
            reason="Not Found",
            status_code=404,
            content="Slack User %s not found" % slack_user,
        )

    @app.route("/checkerboard/github/<github_user>")
    @app.route("/checkerboard/github/<github_user>/")
    def get_slack_user(github_user=None):
        """Returns JSON object mapping Slack user to GitHub user, given
        GitHub user."""
        _precheck()
        if github_user:
            sl_user = app.config["MAPPER"].slack_for_github_user(github_user)
            if sl_user:
                return jsonify({sl_user: github_user})
            raise BackendError(
                reason="Not Found",
                status_code=404,
                content=("No Slack user for GitHub user %s" % github_user),
            )
        else:
            github_user = "<none>"
        raise BackendError(
            reason="Not Found",
            status_code=404,
            content="GitHub User %s not found" % github_user,
        )

    def _init_map():
        if not app.config["MAPPER"]:
            _set_mapper()
        app.config["MAPPER"].wait_for_initialization()

    def _precheck():
        _auth()
        _init_map()

    def _auth():
        if request.authorization is None:
            raise BackendError(
                reason="Unauthorized",
                status_code=401,
                content="No authorization provided.",
            )
        inboundauth = request.authorization
        if inboundauth.username != USER or inboundauth.password != PW:
            raise BackendError(
                reason="Unauthorized",
                status_code=401,
                content="Incorrect authorization.",
            )
        if not app.config["MAPPER"]:
            _set_mapper()

    def _set_mapper():
        mapper = Usermapper(
            bot_token=os.environ["SLACK_BOT_TOKEN"],
            app_token=os.environ["SLACK_APP_TOKEN"],
            field_name=FIELD,
        )
        if not mapper:
            raise BackendError(
                reason="Internal Server Error",
                content="Failed to get mapper object.",
                status_code=500,
            )
        app.config["MAPPER"] = mapper
        SCHED.enter(app.config["CACHE_LIFETIME"], 1, _repeater, ())
        Thread(target=SCHED.run, name="mapbuilder").start()

    def _repeater():
        mapper = app.config["MAPPER"]
        mapper.rebuild_usermap()
        cachelife = app.config["CACHE_LIFETIME"]
        min_cache = 0.6 * len(mapper.usermap)
        if cachelife < min_cache:
            log.warning("Increasing cache lifetime to %f" % min_cache)
            cachelife = min_cache
            app.config["CACHE_LIFETIME"] = cachelife
        SCHED.enter(cachelife, 1, _repeater, ())

    # Back to mainline code: do initialization stuff.
    app.config["MAPPER"] = None
    global log
    # Gross, but efficacious
    log = app.config["LOGGER"]
    app.config["CACHE_LIFETIME"] = CACHE_LIFETIME
    if start_usermapper:
        _init_map()

    if run_standalone:
        app.run(host="0.0.0.0", threaded=True)
    # Otherwise, we're running under uwsgi, and it wants the app.
    return app


def standalone():
    """Entry point for running as its own executable.
    """
    server(run_standalone=True)


if __name__ == "__main__":
    standalone()
