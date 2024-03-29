# Change log

Checkerboard is versioned with [semver](https://semver.org/). Dependencies are updated to the latest available version during each release. Those changes are not noted here explicitly.

Find changes for the upcoming release in the project's [changelog.d directory](https://github.com/lsst-sqre/checkerboard/tree/main/changelog.d/).

<!-- scriv-insert-here -->

## 0.4.0 (2024-02-08)
This release drops support for Python 3.9 and 3.10.  Python 3.11 or later is now required.

- Require Python 3.11 or later and drop Python 3.9 and 3.10 support.
- Rewrite Checkerboard as a [FastAPI](https://fastapi.tiangolo.com/) service.
- Deploy Checkerboard as a [Phalanx](https://phalanx.lsst.io) service.

## 0.3.1 (2021-03-01)

This release drops support for Python 3.7 and 3.8.
Python 3.9 or later is now required.

- Require Python 3.9 and drop Python 3.7 and 3.8 support.
- Add security hardening to the Kustomize Kubernetes manifest.
- Honor logging configuration when logging Slack mapper actions.
- Update all dependencies.

## 0.3.0 (2020-03-04)

With this release, Checkerboard has been rewritten as an [aiohttp](https://docs.aiohttp.org/en/stable/>) application based on the [Safir](https://safir.lsst.io) framework.
The configuration and routes have all changed in this release.

- `/checkerboard` now returns only application metadata.
    For a list of all mappings, use `/checkerboard/slack`.
- Routes no longer support appending trailing slashes.
- The application now requires only one Slack token, which is set using the `CHECKERBOARD_SLACK_TOKEN` environment variable.
- Change the environment variable `CHECKERBOARD_USER` to `CHECKERBOARD_USERNAME` and `CHECKERBOARD_PW` to `CHECKERBOARD_PASSWORD`.
- The expected structure of the Kubernetes secret has changed.
    See `manifests/secret.template.yaml` for the new structure.

## 0.2.0 (2020-02-19)

With this release, the package is now named Checkerboard.
See `README.md` for more information about the naming choice.

- Rename the package in multiple places.
- Rename the Python package from `uservice_ghslacker` to `checkerboard`.
- Change environment variables controlling application settings to start with `CHECKERBOARD_` instead of `GHSLACKER_`.
- Change all routes from `/ghslacker` to `/checkerboard`.
- Base the Docker container on python:3.7 instead of centos:7.
    This saves some setup work and is based on a standard buildpack-deps container.
- Add a trivial test so that the test suite can run.
    More extensive tests will be added later after a refactoring.

## 0.1.1 (2020-02-14)

- Bump dependency on sqre-apikit to pick up a fix for a conflict between older Flask and new werkzeug.

## 0.1.0 (2020-02-13)

- userve-ghslacker can now be deployed through Kustomize.
    The base is located at ``/manifests/base``.
    This means that you can incorporate this application into a specific Kustomize-based application (such as one deployed by Argo CD) with a URL such as `github.com/lsst-sqre/uservice-ghslacker.git//manifests/base?ref=0.1.0`.
    There is a *separate* template for the Secret resource expected by the deployment at `/manifests/secret.template.yaml`.
