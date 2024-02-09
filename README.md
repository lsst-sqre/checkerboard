# Checkerboard

Checkerboard is a [FastAPI](https://fastapi.tiangolo.com/) service to map user identities between systems with their own concepts of identity.
Currently, only mapping between Slack users and GitHub users is supported.
Slack users are associated with GitHub users via a custom field in the Slack profile.
The default field name is "GitHub Username".

This is an Rubin Observatory DM SQuaRE api.lsst.codes microservice, developed with the [Safir](https://safir.lsst.io) framework.

## Usage

Use ``checkerboard run`` to start the service.
By default, it will run on port 8080.
This can be changed with the ``--port`` option.

## Configuration

The following environment variables must be set in Checkerboard's runtime environment.

* `CHECKERBOARD_USERNAME`: The HTTP Basic Authentication user expected
* `CHECKERBOARD_PASSWORD`: The HTTP Basic Authentication password expected
* `CHECKERBOARD_SLACK_TOKEN`: Slack bot token with `users:read` and `users.profile:read` scopes
* `CHECKERBOARD_REDIS_PASSWORD`: The password for Checkerboard to communicate with its Redis instance.

The following environment variables may optionally be set to change default behavior.

* `SAFIR_PROFILE`: Set to `production` to enable production logging
* `SAFIR_LOG_LEVEL`: Set to `DEBUG`, `INFO`, `WARNING`, or `ERROR` to change the log level.
    The default is `INFO`.
* `CHECKERBOARD_PROFILE_FIELD`: The name of the custom field in Slack from which to obtain the GitHub username.
    The default is `GitHub Username`.
* `CHECKERBOARD_REFRESH_INTERVAL`: How frequently (in seconds) to refresh the Slack <-> GitHub mapping.
    This takes about 10 minutes for 2,000 users, so do not lower this too much.
    The default is 3600 (one hour).

## Routes
------

Checkerboard has a `/` health-check route exposing metadata; `/checkerboard/` gives the same data under the `_metadata` key.  This does not require authentication.

It has the standard set of documentation endpoints at `/checkerboard/docs`, `/checkerboard/redoc`, and `/checkerboard/openapi.json`.  These routes, too, do not require authentication.

All other requests must be authenticated with HTTP Basic Authentication using the username and password defined by the ``CHECKERBOARD_USERNAME`` and ``CHECKERBOARD_PASSWORD`` environment variables.  The routes and their expected parameters are available at the documentation endpoints.  They are as follows:

* `/checkerboard/slack`: Returns all known Slack to GitHub user mappings.
    The Slack user ID is the key, and the lowercased representation of the GitHub username (or, more generally, the contents of the field specified in the service) is the value.

* `/checkerboard/slack/<user>`: Returns a JSON object whose key is `<user>`, which is a Slack `id` (*not* a display name), and whose value is the corresponding GitHub user.
      Returns a 404 if either the user ID is not found, or there is no corresponding GitHub user.

* `/checkerboard/github/<user>`: Returns a JSON object whose value is ``<user>`` and whose key is the corresponding Slack user `id`.
    Returns a 404 if there is no GitHub username `<user>` (not case-sensitive) mapped to a Slack user.
    The GitHub username in the returned value will always have the same capitalization as the query, regardless of the actual username at GitHub.

## Deployment

Checkerboard is deployed as a standard [Phalanx](https://phalanx.lsst.io) application.

## Naming

Checkerboard is a (very simple) federated identity service used by the SQuaRE tem at the Rubin Observatory.
A checkerboard is a federation of squares.
