#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


def test_01_get_certificateauthority_query():
    results = GET('/certificateauthority/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
