# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2011 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Views for managing Nova instances.
"""
import datetime
import logging

from django import http
from django import shortcuts
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.datastructures import SortedDict
from django.utils.translation import ugettext as _
import openstackx.api.exceptions as api_exceptions

from horizon.api.base import *

import horizon
from horizon import api
from horizon import forms
from horizon import test


from ..billing import billing_query
from ..forms import DateIntervalForm

LOG = logging.getLogger(__name__)


def _get_datetime(request, prefix):
    try:
        return datetime.datetime(
                int(request.GET['%s_year' % prefix]),
                int(request.GET['%s_month' % prefix]),
                int(request.GET['%s_day'  % prefix]))
    except:
        return datetime.datetime.combine(
            datetime.date.today(), datetime.time(0))


def usage(request, tenant_id):
    datetime_end = _get_datetime(request, "date_end")
    datetime_start = _get_datetime(request, "date_start")
    if datetime_start > datetime_end:
        datetime_start, datetime_end = datetime_end, datetime_start
    if datetime_end - datetime_start < datetime.timedelta(days=1):
        datetime_start -= datetime.timedelta(days=1)
    LOG.debug("%s %s" % (datetime_start, datetime_end))

    dateform = DateIntervalForm()
    dateform['date_start'].field.initial = datetime_start.date()
    dateform['date_end'].field.initial = datetime_end.date()

    usage = {}
    try:
        usage = billing_query(
            request,
            period_start=datetime_start,
            period_end=datetime_end,
            tenant_id=tenant_id,
            include=(
                "instances-long,images-long"
                if tenant_id
                else "instances,images")
            )["projects"]
    except Exception, e:
        LOG.exception(_('Exception in instance usage'))

        messages.error(request, _('Unable to get usage info: %s') % e.message)
    else:
        if tenant_id:
            usage = usage[0]
            for item in usage["instances"]["items"]:
                item["lifetime_day"] = item["lifetime_sec"] / (3600 * 12.0)
            for item in usage["images"]["items"]:
                item["lifetime_day"] = item["lifetime_sec"] / (3600 * 12.0)
    
    template_dir = 'billing/for_tenant' if tenant_id else 'billing/total'
        
    if request.GET.get('format', 'html') == 'csv':
        template_name = '%s/billing.csv' % template_dir
        mimetype = "text/csv"
    else:
        template_name = '%s/index.html' % template_dir
        mimetype = "text/html"

    dash_url = horizon.get_dashboard('nova').get_absolute_url()

    return shortcuts.render(request, template_name, {
            'dateform': dateform,
            'usage': usage,
            'csv_link': '?format=csv',
            'datetime_start': datetime_start,
            'datetime_end': datetime_end,
            'dash_url': dash_url,
            }, content_type=mimetype)


@login_required
def usage_for_tenant(request, tenant_id=None):
    return usage(request, tenant_id or request.user.tenant_id)


@login_required
def usage_total(request, tenant_id=None):
    return usage(request, None)
