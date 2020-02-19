[![Build Status](https://travis-ci.com/lsst-sqre/checkerboard.svg?branch=master)](https://travis-ci.com/lsst-sqre/checkerboard)

# checkerboard

Checkerboard maps user identities between systems with their own concepts of identity.
Currently, only mapping between Slack users and GitHub users is supported.
Slack users are associated with GitHub users via a custom field in the Slack profile.
The default field name is "GitHub Username".

This is an Rubin Observatory DM SQuaRE api.lsst.codes microservice.

## Usage

`checkerboard` will run standalone on port 5000 as an HTTP service or under `uwsgi`.

### Configuration

The following environment variables must be set in Checkerboard's runtime environment.

* `CHECKERBOARD_USER`: The HTTP Basic Authentication user expected
* `CHECKERBOARD_PW`: The HTTP Basic Authentication password expected
* `SLACK_APP_TOKEN`: A Slack user token used to query user profiles
* `SLACK_BOT_TOKEN`: A Slack bot token used for Slack API calls

### Routes

All requests except the `/` health-check route must be authenticated with HTTP Basic Authentication using the username and password defined by the `CHECKERBOARD_USER` and `CHECKERBOARD_PW` environment variables.

* `/`: returns `OK` (used by Google Container Engine Ingress healthcheck)

* `/checkerboard`: Returns a JSON object containing all known maps.
  The Slack user ID is the key, and the lowercased representation of the GitHub username (or, more generally, the contents of the field specified in the service) is the value.

* `/checkerboard/slack/<user>`: Returns a JSON object whose key is `<user>`, which is a Slack `id` (*not* `name`), and whose value is the corresponding GitHub user.
  Returns a 404 if either the user ID is not found, or there is no corresponding GitHub user.

* `/checkerboard/github/<user>`: Returns a JSON object whose value is `<user>` and whose key is the corresponding Slack user `id`.
  Returns a 404 if there is no GitHub username `<user>` (not case-sensitive) mapped to a Slack user.
  The GitHub username in the returned value will always have the same capitalization as the query, regardless of the actual username at GitHub.

## Deployment

Checkerboard supports deployment on Kubernetes via Kustomize using the configuration in `manifests/base`.
It depends on a Kubernetes secret, a template for which can be found in `manifests/secret.template.yaml`.

The deployment manifest is pinned to the corresponding version of the Docker image, and thus pinning to a version of the deployment manifest ensures that one is deploying a known version of the Checkerboard application.
So, for example, one can wrap this deployment in a Kustomization resource such as:

    apiVersion: kustomize.config.k8s.io/v1beta1
    kind: Kustomization

    resources:
      - github.com/lsst-sqre/checkerboard.git//manifests/base?ref=0.2.0
      - resources/secret.yaml

where `resources/secret.yaml` provides the required Kubernetes `Secret` resource via some local mechanism.
This will install version 0.2.0 of the Checkerboard application.

The files in `kubernetes` are from a legacy Rubin Observatory deployment and should be ignored.
They will be removed when that deployment has been retired.

## Naming

Checkerboard is a (very simple) federated identity service used by the SQuaRE tem at the Rubin Observatory.
A checkerboard is a federation of squares.
