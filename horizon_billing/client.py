# vim: tabstop=4 shiftwidth=4 softtabstop=4

from datetime import datetime
import httplib
import urllib
import json
import os
import logging
import urlparse


LOG = logging.getLogger(__name__)


class ClientException(Exception):
    """
    The base exception class for all exceptions this library raises.
    """
    def __init__(self, code, message=None, details=None):
        self.code = code
        self.message = message or self.__class__.message
        self.details = details

    def __str__(self):
        return "%s (HTTP %s)" % (self.message, self.code)

    message = "HTTP error"


class HTTPClient(object):
    def __init__(self, auth_token, management_url):
        self.auth_token = auth_token
        self.management_url = management_url

    def http_log(self, args, kwargs, resp, body):
        if os.environ.get('NOVABILLINGCLIENT_DEBUG', False):
            ch = logging.StreamHandler()
            LOG.setLevel(logging.DEBUG)
            LOG.addHandler(ch)
        elif not LOG.isEnabledFor(logging.DEBUG):
            return

        string_parts = ["curl -i '%s' -X %s" % args]

        for element in kwargs['headers']:
            header = ' -H "%s: %s"' % (element, kwargs['headers'][element])
            string_parts.append(header)

        LOG.debug("REQ: %s\n" % "".join(string_parts))
        if 'body' in kwargs:
            LOG.debug("REQ BODY: %s\n" % (kwargs['body']))
        if resp:
            LOG.debug("RESP: %s\nRESP BODY: %s\n", resp.status, body)

    def request(self, *args, **kwargs):
        kwargs.setdefault('headers', kwargs.get('headers', {}))
        if 'body' in kwargs:
            kwargs['headers']['Content-Type'] = 'application/json'
            kwargs['body'] = json.dumps(kwargs['body'])

        resp, body = None, None
        try:
            parsed = urlparse.urlparse(args[0])
            client = httplib.HTTPConnection(parsed.netloc)
            request_uri = ("?".join([parsed.path, parsed.query])
                           if parsed.query
                           else parsed.path)
            client.request(args[1], request_uri, **kwargs)
            resp = client.getresponse()
            body = resp.read()
        finally:
            self.http_log(args, kwargs, resp, body)
        if resp.status in (400, 401, 403, 404, 408, 409, 413, 500, 501):
            raise ClientException(code=resp.status)

        return (resp, body)

    def _cs_request(self, url, method, **kwargs):
        kwargs.setdefault('headers', {})
        if self.auth_token:
            kwargs['headers']['X-Auth-Token'] = self.auth_token
        resp, body = self.request(self.management_url + url, method,
                                  **kwargs)
        return resp, body

    def get(self, url, **kwargs):
        return self._cs_request(url, 'GET', **kwargs)


def datetime_to_str(dt):
    return ("%sZ" % dt.isoformat()) if isinstance(dt, datetime) else None


def url_escape(s):
    return urllib.quote(s)


class BillingClient(HTTPClient):
    @staticmethod
    def get_resource_tree(resources):
        res_by_id = dict(((res["id"], res) for res in resources))
        for res in resources:
            try:
                parent = res_by_id[res["parent_id"]]
            except KeyError:
                pass
            else:
                parent.setdefault("children", []).append(res)
        return filter(
            lambda res: res["parent_id"] not in res_by_id,
            resources)

    @staticmethod
    def build_resource_tree(bill):

        def calc_cost(res):
            cost = res.get("cost", 0.0)
            for child in res.get("children", ()):
                calc_cost(child)
                cost += child["cost"]
            res["cost"] = cost

        for acc in bill:
            subtree = BillingClient.get_resource_tree(
                acc["resources"])
            acc_cost = 0.0
            for res in subtree:
                calc_cost(res)
                acc_cost += res["cost"]
            acc["cost"] = acc_cost
            acc["resources"] = subtree
        return bill

    def bill(self, account=None, time_period=None,
              period_start=None, period_end=None):
        if account:
            params = ["account={0}".format(url_escape(account))]
        else:
            params = []

        for opt in ["time_period", "period_start", "period_end"]:
            par = locals()[opt]
            if par:
                params.append("{0}={1}".format(
                    opt, url_escape(datetime_to_str(par))))
        req = "/bill"
        if params:
            req = "{0}?{1}".format(req, "&".join(params))
        resp, body = self.get(req)
        return self.build_resource_tree(json.loads(body)["bill"])
