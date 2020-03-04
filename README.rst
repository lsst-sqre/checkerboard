############
Checkerboard
############

Checkerboard maps user identities between systems with their own concepts of identity.
Currently, only mapping between Slack users and GitHub users is supported.
Slack users are associated with GitHub users via a custom field in the Slack profile.
The default field name is "GitHub Username".

This is an Rubin Observatory DM SQuaRE api.lsst.codes microservice, developed with the `Safir <https://safir.lsst.io>`__ framework.

Usage
=====

Use ``checkerboard run`` to start the service.
By default, it will run on port 8080.
This can be changed with the ``--port`` option.

Configuration
-------------

The following environment variables must be set in Checkerboard's runtime environment.

* ``CHECKERBOARD_USERNAME``: The HTTP Basic Authentication user expected
* ``CHECKERBOARD_PASSWORD``: The HTTP Basic Authentication password expected
* ``CHECKERBOARD_SLACK_TOKEN``: Slack bot token with ``users:read`` and ``users.profile:read`` scopes

Routes
------

All requests except the ``/`` health-check route must be authenticated with HTTP Basic Authentication using the username and password defined by the ``CHECKERBOARD_USERNAME`` and ``CHECKERBOARD_PASSWORD`` environment variables.

* ``/``: Returns service metadata with a 200 status (used by Google Container Engine Ingress health check)

* ``/checkerboard``: Returns metadata about the service.

* ``/checkerboard/slack``: Returns all known Slack to GitHub user mappings.
  The Slack user ID is the key, and the lowercased representation of the GitHub username (or, more generally, the contents of the field specified in the service) is the value.

* ``/checkerboard/slack/<user>``: Returns a JSON object whose key is ``<user>``, which is a Slack ``id`` (*not* a display name), and whose value is the corresponding GitHub user.
  Returns a 404 if either the user ID is not found, or there is no corresponding GitHub user.

* ``/checkerboard/github/<user>``: Returns a JSON object whose value is ``<user>`` and whose key is the corresponding Slack user ``id``.
  Returns a 404 if there is no GitHub username ``<user>`` (not case-sensitive) mapped to a Slack user.
  The GitHub username in the returned value will always have the same capitalization as the query, regardless of the actual username at GitHub.

Deployment
==========

Checkerboard supports deployment on Kubernetes via Kustomize using the configuration in ``manifests/base``.
It depends on a Kubernetes secret, a template for which can be found in ``manifests/secret.template.yaml``.

The deployment manifest is pinned to the corresponding version of the Docker image, and thus pinning to a version of the deployment manifest ensures that one is deploying a known version of the Checkerboard application.
So, for example, one can wrap this deployment in a Kustomization resource such as:

.. code-block:: yaml

   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization

   resources:
     - github.com/lsst-sqre/checkerboard.git//manifests/base?ref=0.2.0
     - resources/secret.yaml

where ``resources/secret.yaml`` provides the required Kubernetes ``Secret`` resource via some local mechanism.
This will install version 0.2.0 of the Checkerboard application.

Naming
======

Checkerboard is a (very simple) federated identity service used by the SQuaRE tem at the Rubin Observatory.
A checkerboard is a federation of squares.
