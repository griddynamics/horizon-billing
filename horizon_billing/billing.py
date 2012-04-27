# vim: tabstop=4 shiftwidth=4 softtabstop=4

import logging
from horizon.api.base import *
from .client import BillingClient


LOG = logging.getLogger(__name__)


def billing_api(request):
    management_url = url_for(request, 'nova_billing')
    LOG.debug('billing_api connection created using token "%s"'
                     ' and url "%s"' %
                    (request.user.token, management_url))
    return BillingClient(auth_token=request.user.token,
                         management_url=management_url)
