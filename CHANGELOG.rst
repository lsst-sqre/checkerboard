##########
Change log
##########

0.2.0 (unreleased)
==================

With this release, the package is now named Checkerboard.
See ``README.md`` for more information about the naming choice.

- Rename the package in multiple places.
- Rename the Python package from ``uservice_ghslacker`` to ``checkerboard``.
- Change environment variables controlling application settings to start with ``CHECKERBOARD_`` instead of ``GHSLACKER_``.
- Change all routes from ``/ghslacker`` to ``/checkerboard``.
- Base the Docker container on python:3.7 instead of centos:7.
  This saves some setup work and is based on a standard buildpack-deps container.
- Add a trivial test so that the test suite can run.
  More extensive tests will be added later after a refactoring.

0.1.1 (2020-02-14)
==================

- Bump dependency on sqre-apikit to pick up a fix for a conflict between older Flsk and new werkzeug.

0.1.0 (2020-02-13)
==================

- userve-ghslacker can now be deployed through Kustomize.
  The base is located at ``/manifests/base``.
  This means that you can incorporate this application into a specific Kustomize-based application (such as one deployed by Argo CD) with a URL such as ``github.com/lsst-sqre/uservice-ghslacker.git//manifests/base?ref=0.1.0``.
  There is a *separate* template for the Secret resource expected by the deployment at ``/manifests/secret.template.yaml``.
