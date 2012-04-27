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


from ..billing import billing_api
from ..forms import DateIntervalForm


LOG = logging.getLogger(__name__)


def total_seconds(td):
    """This function is added for portability
    because timedelta.total_seconds() 
    was introduced only in python 2.7."""
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


def str_to_datetime(dtstr):
    """
    Convert string to datetime.datetime. String should be in ISO 8601 format.
    The function returns ``None`` for invalid date string.
    """
    if not dtstr:
        return None
    if dtstr.endswith("Z"):
        dtstr = dtstr[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.datetime.strptime(dtstr, fmt)
        except ValueError:
            pass
    return None


def _get_datetime(request, prefix):
    try:
        return datetime.datetime(
                int(request.GET['%s_year' % prefix]),
                int(request.GET['%s_month' % prefix]),
                int(request.GET['%s_day'  % prefix]))
    except:
        return datetime.datetime.combine(
            datetime.date.today(), datetime.time(0))


def _linear_bill(bill):
    linear_bill = []
    def print_res(res, depth):
        res["depth"] = depth * 16
        res["hier"] = "+" * depth
        try:
            res["lifetime_day"] = total_seconds(
                (str_to_datetime(res["destroyed_at"]) 
                 or datetime.datetime.utcnow()) -
                str_to_datetime(res["created_at"])) / 3600 * 24.0
        except TypeError:
            res["lifetime_day"] = "?"
        linear_bill.append(res)
        depth += 1
        for child in res.get("children", ()):
            print_res(child, depth)
        res["children"] = ()

    for acc in bill:
        linear_bill = []
        for res in sorted(acc["resources"], key=lambda res: (res["rtype"], res["name"])):
            print_res(res, 0)
        acc["resources"] = linear_bill 


def get_bill(request, tenant_id):
    datetime_end = _get_datetime(request, "date_end")
    datetime_start = _get_datetime(request, "date_start")
    if datetime_start > datetime_end:
        datetime_start, datetime_end = datetime_end, datetime_start
    if datetime_end - datetime_start < datetime.timedelta(days=1):
        datetime_start -= datetime.timedelta(days=1)

    dateform = DateIntervalForm()
    dateform['date_start'].field.initial = datetime_start.date()
    dateform['date_end'].field.initial = datetime_end.date()

    bill = {}
    rtype_names = set()
    try:
        bill = billing_api(request).bill(
            period_start=datetime_start,
            period_end=datetime_end,
            account=tenant_id)
    except Exception, e:
        LOG.exception(_('Exception in bill'))

        messages.error(request, _('Unable to get the bill: %s') % e.message)
    else:
        if tenant_id:
            _linear_bill(bill)
            bill = bill[0]
        else:
            for acc in bill:
                rtypes = {}
                for res in acc["resources"]:
                    rtypes[res["rtype"]] = rtypes.get(res["rtype"], 0.0) + res["cost"]
                del acc["resources"]
                acc["rtypes"] = rtypes
                rtype_names |= set(rtypes.iterkeys())
            rtype_names = sorted(rtype_names)
            for acc in bill:
                rtypes = acc["rtypes"]
                acc["rtypes"] = [rtypes.get(name, 0.0) for name in rtype_names]
    
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
            'bill': bill,
            'csv_link': '?format=csv',
            'datetime_start': datetime_start,
            'datetime_end': datetime_end,
            'dash_url': dash_url,
            'rtype_names': rtype_names,
            }, content_type=mimetype)


@login_required
def bill_for_tenant(request, tenant_id=None):
    return get_bill(request, tenant_id or request.user.tenant_id)


@login_required
def bill_total(request, tenant_id=None):
    return get_bill(request, None)
