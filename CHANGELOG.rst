##########
Change log
##########

0.1.0 (unreleased)
==================

- userve-ghslacker can now be deployed through Kustomize.
  The base is located at ``/manifests/base``.
  This means that you can incorporate this application into a specific Kustomize-based application (such as one deployed by Argo CD) with a URL such as ``github.com/lsst-sqre/uservice-ghslacker.git//manifests/base?ref=0.1.0``.
  There is a *separate* template for the Secret resource expected by the deployment at ``/manifests/secret.template.yaml``.
