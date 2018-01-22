[![Build Status](https://travis-ci.org/lsst-sqre/uservice-ghslacker.svg?branch=master)](https://travis-ci.org/lsst-sqre/uservice-ghslacker)

# sqre-uservice-ghslacker

LSST DM SQuaRE api.lsst.codes-compliant microservice wrapper.  TODO

## Usage

`sqre-uservice-ghslacker` will run standalone on port
5000 or under `uwsgi`.  It responds to the following routes:

### Routes

* `/`: returns `OK` (used by Google Container Engine Ingress healthcheck)

* `/ghslacker`: TODO

### Returned Structure

The returned structure is JSON.  TODO.
