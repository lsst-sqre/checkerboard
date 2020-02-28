#!/usr/bin/env python3

from __future__ import annotations

import logging
import time
from threading import Lock, Thread
from typing import TYPE_CHECKING

from requests_futures.sessions import FuturesSession

if TYPE_CHECKING:
    from requests import Response
    from typing import Any, Dict, List, Optional


class Usermapper(object):
    """Build/maintain map of Slack usernames to GH usernames, based on a
    provided field, which for LSST is "GitHub Username".
    """

    usermap: Dict[str, str] = {}
    _userlist: List[str] = []
    usermap_initialized = False

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        field_name: str = "GitHub Username",
        max_workers: int = 50,
    ) -> None:
        self.bot_token = bot_token
        self.app_token = app_token
        self.mutex = Lock()
        self.session = FuturesSession(max_workers=max_workers)
        self.field_id = self._get_field_id(field_name)
        self.session.max_workers = min(max_workers, len(self._userlist))
        logging.debug("Building usermap.")
        Thread(target=self.rebuild_usermap, name="mapbuilder").start()

    def github_for_slack_user(self, user: str) -> Optional[str]:
        """Return the usermap entry for a given Slack user (which should be
        the GitHub Username field).  None if there is no match.  Case-
        sensitive on the Slack side, forced to lower on the GitHub side.
        """
        self._check_initialization()
        u = self.usermap.get(user)
        if u:
            return u.lower()
        else:
            return None

    def slack_for_github_user(self, user: str) -> Optional[str]:
        """Given a GitHub Username, return the first Slack username that has
        that name in the GitHub Username field, or None.  Not case-sensitive.
        """
        for slacker in self.usermap:
            if self.usermap[slacker].lower() == user.lower():
                return slacker
        self._check_initialization()
        return None

    def rebuild_usermap(self) -> None:
        """Rebuild the entire Slack user -> GitHub user map.
        """
        logging.debug("Beginning usermap rebuild.")
        newmap = {}
        response = {}
        self._rebuild_userlist()
        for user in self._userlist:
            response[user] = self._retrieve_github_user_response(user)
        for user in response:
            resp = self._slackcheck(response[user])
            if "profile" in resp:
                ghuser = self._process_profile(resp["profile"])
                if ghuser:
                    self.mutex.acquire()
                    try:
                        newmap[user] = ghuser
                    finally:
                        self.mutex.release()
        self.mutex.acquire()
        self.usermap = newmap
        self.usermap_initialized = True
        self.mutex.release()
        logging.debug("Usermap built.")

    def check_initialization(self) -> bool:
        """Returns True if the usermap has been built, False otherwise.
        """
        try:
            self._check_initialization()
            return True
        except RuntimeError:
            return False

    def wait_for_initialization(self, delay: int = 1) -> None:
        """Polls, with specified delay, until the usermap has been built.
        """
        while True:
            if self.check_initialization():
                return
            logging.debug("Usermap not initialized; sleeping %d s." % delay)
            time.sleep(delay)

    def _rebuild_userlist(self) -> None:
        """Get all users of this Slack instance by id.
        """
        params = {
            "Content-Type": "application/x-www-form/urlencoded",
            "token": self.bot_token,
        }
        method = "users.list"
        moar = True
        userlist: List[Dict[str, Any]] = []
        while moar:
            resp = self._get_slack_response(method, params)
            retval = self._slackcheck(resp)
            userlist = userlist + retval["members"]
            if (
                "response_metadata" in retval
                and "next_cursor" in retval["response_metadata"]
                and retval["response_metadata"]["next_cursor"]
            ):
                params["cursor"] = retval["response_metadata"]["next_cursor"]
            else:
                moar = False
        self.mutex.acquire()
        self._userlist = [u["id"] for u in userlist]
        self.mutex.release()

    def _get_field_id(self, field_name: str) -> Optional[str]:
        method = "team.profile.get"
        params = {
            "Content-Type": "application/x-www-form/urlencoded",
            "token": self.app_token,
        }
        resp = self._get_slack_response(method, params)
        retval = self._slackcheck(resp)
        if (
            "profile" in retval
            and retval["profile"]
            and "fields" in retval["profile"]
            and retval["profile"]["fields"]
        ):
            for fld in retval["profile"]["fields"]:
                if (
                    "label" in fld
                    and "id" in fld
                    and fld["label"] == field_name
                ):
                    return fld["id"]
        return None

    def _check_initialization(self) -> None:
        if not self.usermap_initialized:
            raise RuntimeError("Usermap not initialized.")

    def _retrieve_github_user_response(self, user: str) -> Response:
        method = "users.profile.get"
        params = {
            "Content-Type": "application/x-www-form/urlencoded",
            "token": self.app_token,
            "user": user,
        }
        return self._get_slack_response(method, params)

    def _process_profile(self, profile: Dict[str, Any]) -> Optional[str]:
        ghname = None
        fid = self.field_id
        dname = profile["display_name_normalized"]
        if (
            "fields" in profile
            and profile["fields"]
            and fid in profile["fields"]
            and "value" in profile["fields"][fid]
        ):
            ghname = profile["fields"][fid]["value"]
        logging.debug("Slack user %s -> GitHub user %r" % (dname, ghname))
        return ghname

    def _get_slack_response(
        self, method: str, params: Dict[str, str]
    ) -> Response:
        url = "https://slack.com/api/" + method
        future = self.session.get(url, params=params)
        resp = future.result()
        return resp

    def _slackcheck(self, resp: Response) -> Dict[str, Any]:
        sc = resp.status_code
        if sc == 429:
            delay = int(resp.headers["Retry-After"])
            logging.warning("Slack API rate-limited.  Waiting %d s." % delay)
            time.sleep(delay)
            logging.warning("Retrying request.")
            req = resp.request
            future = self.session.get(req)
            resp = future.result()
        resp.raise_for_status()
        retval = resp.json()
        if not retval["ok"]:
            errstr = "Slack API request '%s' failed: %s" % (
                resp.request.url,
                retval["error"],
            )
            raise RuntimeError(errstr)
        return retval
