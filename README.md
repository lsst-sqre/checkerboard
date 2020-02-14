[![Build Status](https://travis-ci.com/lsst-sqre/uservice-ghslacker.svg?branch=master)](https://travis-ci.com/lsst-sqre/uservice-ghslacker)

# sqre-uservice-ghslacker

LSST DM SQuaRE api.lsst.codes-compliant microservice wrapper.  This
service provides a mapping between Slack users and a username defined in
a custom field in the Slack profile; in our case we are using "GitHub
Username", hence the service name.

## Usage

`sqre-uservice-ghslacker` will run standalone on port
5000 or under `uwsgi`.  It responds to the following routes:

### Routes

* `/`: returns `OK` (used by Google Container Engine Ingress healthcheck)

* `/ghslacker`: returns a JSON object containing all known maps.  The
  Slack user ID is the key, and the lowercased representation of the
  GitHub username (or, more generally, the contents of the field
  specified in the service) is the value.

* `/ghslacker/slack/<user>`: returns a JSON object whose key is `<user>`
  (which is a Slack `id` (*not* `name`), and whose value is the
  corresponding GitHub user.  Returns a 404 if either the user ID is not
  found, or there is no corresponding GitHub user.
  
* `/ghslacker/github/<user>`: returns a JSON object whose value is
  `<user>` and whose key is the corresponding Slack user `id`.  Returns
  a 404 if there is no GitHub username <user> (not case-sensitive)
  mapped to a Slack user.  The GitHub username in the returned value
  will always have the same capitalization as the query, regardless of
  the actual username at GitHub.

### Returned Structure

The returned structure is JSON.  It is an object made of key/value pairs,
where the key is the Slack username and the value is the corresponding
GitHub username.
