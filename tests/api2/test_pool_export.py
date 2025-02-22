#!/usr/bin/env python3
import pytest
from pytest_dependency import depends

from middlewared.client import ClientException
from middlewared.test.integration.utils import call, mock

import os
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT
from auto_config import pool_name, ha, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


def test_systemdataset_migrate_error(request):
    depends(request, ["pool_04"], scope="session")
    """
    On HA this test will fail with the error below if failover is enable:
    [ENOTSUP] Disable failover before exporting last pool on system.
    """

    # Disable Failover
    if ha is True:
        results = PUT('/failover/', {"disabled": True, "master": True})
        assert results.status_code == 200, results.text

    pool = call("pool.query", [["name", "=", pool_name]], {"get": True})

    with mock("systemdataset.update", """\
        from middlewared.service import job, CallError

        @job()
        def mock(self, job, *args):
            raise CallError("Test error")
    """):
        with pytest.raises(ClientException) as e:
            call("pool.export", pool["id"], job=True)

        assert e.value.error == (
            "[EFAULT] This pool contains system dataset, but its reconfiguration failed: [EFAULT] Test error"
        )

    # Enable back Failover.
    if ha is True:
        results = PUT('/failover/', {"disabled": False, "master": True})
        assert results.status_code == 200, results.text
