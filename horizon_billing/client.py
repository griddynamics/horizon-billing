# vim: tabstop=4 shiftwidth=4 softtabstop=4


import httplib
import urllib
import json
import os
import logging
import urlparse


_logger = logging.getLogger(__name__)


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
            _logger.setLevel(logging.DEBUG)
            _logger.addHandler(ch)
        elif not _logger.isEnabledFor(logging.DEBUG):
            return

        string_parts = ["curl -i '%s' -X %s" % args]

        for element in kwargs['headers']:
            header = ' -H "%s: %s"' % (element, kwargs['headers'][element])
            string_parts.append(header)

        _logger.debug("REQ: %s\n" % "".join(string_parts))
        if 'body' in kwargs:
            _logger.debug("REQ BODY: %s\n" % (kwargs['body']))
        if resp:
            _logger.debug("RESP: %s\nRESP BODY: %s\n", resp.status, body)

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
    return ("%sZ" % dt.isoformat()) if dt else None


class BillingClient(HTTPClient):
    def query(self, tenant_id=None, time_period=None,
              period_start=None, period_end=None,
              include=None):
        params = []
        req = "/projects"
        local_vars = locals()
        for var in ("time_period", "include",):
            if local_vars[var]:
                params.append("%s=%s" % (var, urllib.quote(local_vars[var])))
        for var in ("period_start", "period_end"):
            if local_vars[var]:
                params.append("%s=%s" % (var, urllib.quote(
                            datetime_to_str(local_vars[var]))))
        if tenant_id is not None:
            req = "%s/%s" % (req, tenant_id)
        if params:
            req = "%s?%s" % (req, "&".join(params))
        resp, body = self.get(req)
        return json.loads(body)
