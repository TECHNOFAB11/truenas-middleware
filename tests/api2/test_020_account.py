#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST
from auto_config import dev_test

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


def delete_group_delete_users(delete_users):
    results = POST("/user/", {
        "username": "test",
        "group_create": True,
        "full_name": "Test",
        "password_disabled": True,
    })
    assert results.status_code == 200, results.text
    user_id = results.json()

    results = GET(f"/user/id/{user_id}")
    assert results.status_code == 200, results.text
    group_id = results.json()["group"]["id"]

    results = DELETE(f"/group/id/{group_id}", {"delete_users": delete_users})
    assert results.status_code == 200, results.text

    return user_id, group_id


def test_01_delete_group_delete_users():
    user_id, group_id = delete_group_delete_users(True)

    results = GET(f"/user/id/{user_id}")
    assert results.status_code == 404, results.text


def test_01_delete_group_no_delete_users():
    user_id, group_id = delete_group_delete_users(False)

    results = GET(f"/user/id/{user_id}")
    assert results.status_code == 200, results.text
    assert results.json()["group"]["bsdgrp_group"] == "nogroup"

    results = DELETE(f"/user/id/{user_id}")
    assert results.status_code == 200, results.text
