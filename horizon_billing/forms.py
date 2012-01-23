import datetime

import django.forms

import horizon
from horizon import forms


class DateIntervalForm(forms.Form):
    """
    A :class:`Form <django:django.forms.Form>` subclass that includes fields
    called ``date_start`` and ``date_end`` which uses :class:`.SelectDateWidget`.
    """
    date_start = django.forms.DateField(widget=forms.SelectDateWidget(
        years=range(datetime.date.today().year, 2009, -1),
        skip_day_field=False))

    date_end = django.forms.DateField(widget=forms.SelectDateWidget(
        years=range(datetime.date.today().year, 2009, -1),
        skip_day_field=False))
