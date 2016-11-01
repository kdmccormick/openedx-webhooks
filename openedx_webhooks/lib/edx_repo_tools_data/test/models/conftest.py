# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import datetime

import pytest

from openedx_webhooks.lib.edx_repo_tools_data.models import People, Person


@pytest.fixture
def active_data():
    data = {'active-person': {
        'agreement': 'individual',
    }}
    return data


@pytest.fixture
def expired_data():
    data = {'expired-person': {
        'agreement': 'institution',
        'expires_on': datetime.date(2012, 10, 1),
        'institution': 'edX',
    }}
    return data


@pytest.fixture
def active_person(active_data):
    k, v = list(active_data.items())[0]
    return Person(k, v)


@pytest.fixture
def active_edx_person():
    person = Person('active-person', {
        'agreement': 'institution',
        'institution': 'edX',
    })
    return person


@pytest.fixture
def active_non_edx_person():
    person = Person('active-person', {
        'agreement': 'institution',
        'institution': 'Shield',
    })
    return person


@pytest.fixture
def expired_person(expired_data):
    k, v = list(expired_data.items())[0]
    return Person(k, v)


@pytest.fixture
def before():
    data = {
        datetime.date(2016, 1, 9): {},
        datetime.date(2016, 7, 29): {},
        datetime.date(2016, 8, 8): {},
    }
    return data


@pytest.fixture
def before_expired_person(before):
    person = Person('expired-before-person', {
        'agreement': 'none',
        'before': before,
    })
    return person


@pytest.fixture
def people(active_data, expired_data):
    data = active_data.copy()
    data.update(expired_data)
    return People(data)
