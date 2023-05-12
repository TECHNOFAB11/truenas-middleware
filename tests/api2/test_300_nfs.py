#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import contextlib
import urllib.parse
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST, DELETE, wait_on_job
from functions import make_ws_request
from auto_config import pool_name, ha, hostname
from auto_config import dev_test, password, user
from protocols import SSH_NFS
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')

if ha and "virtual_ip" in os.environ:
    ip = os.environ["virtual_ip"]
else:
    from auto_config import ip
MOUNTPOINT = f"/tmp/nfs-{hostname}"
dataset = f"{pool_name}/nfs"
dataset_url = dataset.replace('/', '%2F')
NFS_PATH = "/mnt/" + dataset


def parse_exports():
    results = SSH_TEST("cat /etc/exports", user, password, ip)
    assert results['result'] is True, f"rc={results['return_code']}, {results['output']}, {results['stderr']}"
    exp = results['output'].splitlines()
    rv = []
    for idx, line in enumerate(exp):
        if not line or line.startswith('\t'):
            continue

        entry = {"path": line.strip()[1:-2], "opts": []}

        i = idx + 1
        while i < len(exp):
            if not exp[i].startswith('\t'):
                break

            e = exp[i].strip()
            host, params = e.split('(', 1)
            entry['opts'].append({
                "host": host,
                "parameters": params[:-1].split(",")
            })
            i += 1

        rv.append(entry)

    return rv


def parse_server_config(fname="local.conf"):
    results = SSH_TEST(f"cat /etc/nfs.conf.d/{fname}", user, password, ip)
    assert results['result'] is True, f"rc={results['return_code']}, {results['output']}, {results['stderr']}"
    conf = results['output'].splitlines()
    rv = {'nfsd': {}, 'mountd': {}, 'statd': {}, 'lockd': {}}
    section = ''

    for line in conf:
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            section = line.split('[')[1].split(']')[0]
            continue

        k, v = line.split(" = ", 1)
        rv[section].update({k: v})

    return rv


def confirm_nfsd_processes(expected=16):
    '''
    Confirm the expected number of nfsd processes are running
    '''
    result = SSH_TEST("cat /proc/fs/nfsd/threads", user, password, ip)
    assert int(result['output']) == expected, result


def confirm_mountd_processes(expected=16):
    '''
    Confirm the expected number of mountd processes are running
    '''
    rx_mountd = r"rpc\.mountd"
    result = SSH_TEST(f"ps -ef | grep '{rx_mountd}' | wc -l", user, password, ip)
    # We subtract one to account for the rpc.mountd thread manager
    assert int(result['output']) - 1 == expected


def confirm_rpc_processes(expected=['idmap', 'bind', 'statd']):
    '''
    Confirm the expected rpc processes are running
    '''

    rx_mountd = r"rpc\.mountd"
    result = SSH_TEST(f"ps -ef | grep '{rx_mountd}' | wc -l", user, password, ip)
    # We subtract one to account for the rpc.mountd thread manager
    assert int(result['output']) - 1 == expected


class NFS_CONFIG:
    '''
    This is used to restore the NFS config to it's original state
    '''
    default_nfs_config = {}


def save_nfs_config():
    exclude = ['id', 'v4_krb_enabled', 'v4_owner_major']
    get_conf_cmd = {'msg': 'method', 'method': 'nfs.config', 'params': []}
    res = make_ws_request(ip, get_conf_cmd)
    assert res.get('error') is None, res
    NFS_CONFIG.default_nfs_config = res['result']
    [NFS_CONFIG.default_nfs_config.pop(key) for key in exclude]


def restore_nfs_config():
    set_conf_cmd = {'msg': 'method', 'method': 'nfs.update', 'params': [NFS_CONFIG.default_nfs_config]}
    res = make_ws_request(ip, set_conf_cmd)
    assert res.get('error') is None, res


@contextlib.contextmanager
def nfs_dataset(name, options=None, acl=None, mode=None):
    assert "/" not in name

    dataset = f"{pool_name}/{name}"

    result = POST("/pool/dataset/", {"name": dataset, **(options or {})})
    assert result.status_code == 200, result.text

    if acl is None:
        result = POST("/filesystem/setperm/", {'path': f"/mnt/{dataset}", "mode": mode or "777"})
    else:
        result = POST("/filesystem/setacl/", {'path': f"/mnt/{dataset}", "dacl": acl})

    assert result.status_code == 200, result.text
    job_status = wait_on_job(result.json(), 180)
    assert job_status["state"] == "SUCCESS", str(job_status["results"])

    try:
        yield dataset
    finally:
        # dataset may be busy
        sleep(10)
        result = DELETE(f"/pool/dataset/id/{urllib.parse.quote(dataset, '')}/")
        retry = 6
        # Under some circumstances, the dataset can balk at being deleted
        # leaving the dataset mounted which then buggers up subsequent tests
        while result.status_code != 200 and retry > 0:
            sleep(10)
            result = DELETE(f"/pool/dataset/id/{urllib.parse.quote(dataset, '')}/")
            retry -= 1
        assert result.status_code == 200, result.text


@contextlib.contextmanager
def nfs_share(path, options=None):
    results = POST("/sharing/nfs/", {
        "path": path,
        **(options or {}),
    })
    assert results.status_code == 200, results.text
    id = results.json()["id"]

    try:
        yield id
    finally:
        result = DELETE(f"/sharing/nfs/id/{id}/")
        assert result.status_code == 200, result.text


@contextlib.contextmanager
def nfs_config(options=None):
    '''
    Use this to restore settings after the test
    '''
    get_conf = {'msg': 'method', 'method': 'nfs.config', 'params': []}
    restore_conf = {'msg': 'method', 'method': 'nfs.update', 'params': []}

    try:
        res = make_ws_request(ip, get_conf)
        assert res.get('error') is None, res
        excl = ['id', 'v4_krb_enabled', 'v4_owner_major']
        nfsconf = res['result']
        [nfsconf.pop(key) for key in excl]
        restore_conf.update({'params': [nfsconf]})
        yield
    finally:
        res = make_ws_request(ip, restore_conf)
        assert res.get('error') is None, res


# Enable NFS server
def test_01_creating_the_nfs_server():
    # initialize default_nfs_config for later restore
    save_nfs_config()

    payload = {
        "servers": 10,
        "mountd_port": 618,
        "allow_nonroot": False,
        "udp": False,
        "rpcstatd_port": 871,
        "rpclockd_port": 32803,
        "protocols": ["NFSV3", "NFSV4"]
    }
    results = PUT("/nfs/", payload)
    assert results.status_code == 200, results.text
    # The service is not yet enabled, so we cannot yet confirm the settings


def test_02_creating_dataset_nfs(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"name": dataset}
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_03_changing_dataset_permissions_of_nfs_dataset(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        "acl": [],
        "mode": "777",
        "user": "root",
        "group": 'root'
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text
    global job_id
    job_id = results.json()


def test_04_verify_the_job_id_is_successfull(request):
    depends(request, ["pool_04"], scope="session")
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_05_creating_a_nfs_share_on_nfs_PATH(request):
    depends(request, ["pool_04"], scope="session")
    global nfsid
    paylaod = {"comment": "My Test Share",
               "path": NFS_PATH,
               "security": ["SYS"]}
    results = POST("/sharing/nfs/", paylaod)
    assert results.status_code == 200, results.text
    nfsid = results.json()['id']


def test_06_starting_nfs_service_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT("/service/id/nfs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_07_checking_to_see_if_nfs_service_is_enabled_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["enable"] is True, results.text


def test_08_starting_nfs_service(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"service": "nfs"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)
    confirm_nfsd_processes(10)
    confirm_mountd_processes(10)


def test_09_checking_to_see_if_nfs_service_is_running(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@pytest.mark.parametrize('vers', [3, 4])
def test_10_perform_basic_nfs_ops(request, vers):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    with SSH_NFS(ip, NFS_PATH, vers=vers, user=user, password=password, ip=ip) as n:
        n.create('testfile')
        n.mkdir('testdir')
        contents = n.ls('.')
        assert 'testdir' in contents
        assert 'testfile' in contents

        n.unlink('testfile')
        n.rmdir('testdir')
        contents = n.ls('.')
        assert 'testdir' not in contents
        assert 'testfile' not in contents


def test_11_perform_server_side_copy(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    with SSH_NFS(ip, NFS_PATH, vers=4, user=user, password=password, ip=ip) as n:
        n.server_side_copy('ssc1', 'ssc2')


def test_19_updating_the_nfs_service(request):
    """
    This test verifies that service can be updated in general,
    and also that the 'servers' key can be altered.
    Latter goal is achieved by reading the nfs config file
    and verifying that the value here was set correctly.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    results = PUT("/nfs/", {"servers": "50"})
    assert results.status_code == 200, results.text

    s = parse_server_config()
    assert int(s['nfsd']['threads']) == 50, str(s)
    assert int(s['mountd']['threads']) == 50, str(s)

    confirm_nfsd_processes(50)
    confirm_mountd_processes(50)


def test_20_update_nfs_share(request):
    depends(request, ["pool_04"], scope="session")
    nfsid = GET('/sharing/nfs?comment=My Test Share').json()[0]['id']
    payload = {"security": []}
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text


def test_21_checking_to_see_if_nfs_service_is_enabled(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_31_check_nfs_share_network(request):
    """
    Verify that adding a network generates an appropriate line in exports
    file for same path. Sample:

    "/mnt/dozer/nfs"\
        192.168.0.0/24(sec=sys,rw,subtree_check)\
        192.168.1.0/24(sec=sys,rw,subtree_check)
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    networks_to_test = ["192.168.0.0/24", "192.168.1.0/24"]

    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'networks': networks_to_test})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)

    exports_networks = [x['host'] for x in parsed[0]['opts']]
    diff = set(networks_to_test) ^ set(exports_networks)
    assert len(diff) == 0, f'diff: {diff}, exports: {parsed}'

    # Reset to default
    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'networks': []})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    exports_networks = [x['host'] for x in parsed[0]['opts']]
    assert len(exports_networks) == 1, str(parsed)
    assert exports_networks[0] == '*', str(parsed)


# Parameters for test_32
hostnames_to_test = [
    # Valid hostnames (IP addresses) and netgroup
    (["192.168.0.69", "192.168.0.70", "@fakenetgroup"], True),
    # Valid wildcarded hostnames
    (["asdfnm-*", "?-asdfnm-*", "asdfnm[0-9]", "nmix?-*dev[0-9]"], True),
    # Valid wildcarded hostname with valid 'domains'
    (["asdfdm-*.example.com", "?-asdfdm-*.ixsystems.com",
      "asdfdm[0-9].example.com", "dmix?-*dev[0-9].ixsystems.com"], True),
    # Invalid hostnames
    (["-asdffail", "*.asdffail.com", "*.*.com", "bozofail.?.*"], False),
    # Mix of valid and invalid hostnames
    (["asdfdm[0-9].example.com", "-asdffail",
      "devteam-*.ixsystems.com", "*.asdffail.com"], False)
]


@pytest.mark.parametrize("hostlist,ExpectedToPass", hostnames_to_test)
def test_32_check_nfs_share_hosts(request, hostlist, ExpectedToPass):
    """
    Verify that adding a network generates an appropriate line in exports
    file for same path. Sample:

    "/mnt/dozer/nfs"\
        192.168.0.69(sec=sys,rw,subtree_check)\
        192.168.0.70(sec=sys,rw,subtree_check)\
        @fakenetgroup(sec=sys,rw,subtree_check)

    host name handling in middleware:
        If the host name contains no wildcard or special chars,
            then we test it with a look up
        else we apply the host name rules and skip the look up

    The rules for the host field are:
    - Dashes are allowed, but a level cannot start or end with a dash, '-'
    - Only the left most level may contain special characters: '*','?' and '[]'
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'hosts': hostlist})
    if ExpectedToPass:
        assert results.status_code == 200, results.text
    else:
        assert results.status_code != 200, results.text

    # Check the exports file
    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    exports_hosts = [x['host'] for x in parsed[0]['opts']]
    if ExpectedToPass:
        # The entry should be present
        diff = set(hostlist) ^ set(exports_hosts)
        assert len(diff) == 0, f'diff: {diff}, exports: {parsed}'
    else:
        # The entry should not be present
        assert len(exports_hosts) == 1, str(parsed)

    # Reset to default should always pass
    cleanup_results = PUT(f"/sharing/nfs/id/{nfsid}/", {'hosts': []})
    assert cleanup_results.status_code == 200, results.text
    # Check the exports file to confirm it's clear
    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    exports_hosts = [x['host'] for x in parsed[0]['opts']]
    assert len(exports_hosts) == 1, str(parsed)


def test_33_check_nfs_share_ro(request):
    """
    Verify that toggling `ro` will cause appropriate change in
    exports file. We also verify with write tests on a local mount.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")

    # Make sure we end up in the original state with 'rw'
    try:
        # Confirm 'rw' initial state and create a file and dir
        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        assert "rw" in parsed[0]['opts'][0]['parameters'], str(parsed)

        # Create the file and dir
        with SSH_NFS(ip, NFS_PATH, user=user, password=password, ip=ip) as n:
            n.create("testfile_should_pass")
            n.mkdir("testdir_should_pass")

        # Change to 'ro'
        results = PUT(f"/sharing/nfs/id/{nfsid}/", {'ro': True})
        assert results.status_code == 200, results.text

        # Confirm 'ro' state and behavior
        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        assert "rw" not in parsed[0]['opts'][0]['parameters'], str(parsed)

        # Attempt create and delete
        with SSH_NFS(ip, NFS_PATH, user=user, password=password, ip=ip) as n:
            with pytest.raises(RuntimeError) as re:
                n.create("testfile_should_fail")
                assert False, "Should not have been able to create a new file"
            assert 'cannot touch' in str(re), re

            with pytest.raises(RuntimeError) as re:
                n.mkdir("testdir_should_fail")
                assert False, "Should not have been able to create a new directory"
            assert 'cannot create directory' in str(re), re

    finally:
        results = PUT(f"/sharing/nfs/id/{nfsid}/", {'ro': False})
        assert results.status_code == 200, results.text

        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        assert "rw" in parsed[0]['opts'][0]['parameters'], str(parsed)

        # Cleanup the file and dir
        with SSH_NFS(ip, NFS_PATH, user=user, password=password, ip=ip) as n:
            n.unlink("testfile_should_pass")
            n.rmdir("testdir_should_pass")


def test_34_check_nfs_share_maproot(request):
    """
    root squash is always enabled, and so maproot accomplished through
    anonuid and anongid

    Sample:
    "/mnt/dozer/NFSV4"\
        *(sec=sys,rw,anonuid=65534,anongid=65534,subtree_check)
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    payload = {
        'maproot_user': 'nobody',
        'maproot_group': 'nogroup'
    }
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)

    params = parsed[0]['opts'][0]['parameters']
    assert 'anonuid=65534' in params, str(parsed)
    assert 'anongid=65534' in params, str(parsed)

    """
    setting maproot_user and maproot_group to root should
    cause us to append "not_root_squash" to options.
    """
    payload = {
        'maproot_user': 'root',
        'maproot_group': 'root'
    }
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    params = parsed[0]['opts'][0]['parameters']
    assert 'no_root_squash' in params, str(parsed)
    assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)

    """
    Second share should have normal (no maproot) params.
    """
    second_share = f'/mnt/{pool_name}/second_share'
    with nfs_dataset('second_share'):
        with nfs_share(second_share):
            parsed = parse_exports()
            assert len(parsed) == 2, str(parsed)

            params = parsed[0]['opts'][0]['parameters']
            assert 'no_root_squash' in params, str(parsed)

            params = parsed[1]['opts'][0]['parameters']
            assert 'no_root_squash' not in params, str(parsed)
            assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)

    payload = {
        'maproot_user': '',
        'maproot_group': ''
    }
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    params = parsed[0]['opts'][0]['parameters']

    assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)


def test_35_check_nfs_share_mapall(request):
    """
    mapall is accomplished through anonuid and anongid and
    setting 'all_squash'.

    Sample:
    "/mnt/dozer/NFSV4"\
        *(sec=sys,rw,all_squash,anonuid=65534,anongid=65534,subtree_check)
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    payload = {
        'mapall_user': 'nobody',
        'mapall_group': 'nogroup'
    }
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)

    params = parsed[0]['opts'][0]['parameters']
    assert 'anonuid=65534' in params, str(parsed)
    assert 'anongid=65534' in params, str(parsed)
    assert 'all_squash' in params, str(parsed)

    payload = {
        'mapall_user': '',
        'mapall_group': ''
    }
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    params = parsed[0]['opts'][0]['parameters']

    assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)
    assert 'all_squash' not in params, str(parsed)


def test_36_check_nfsdir_subtree_behavior(request):
    """
    If dataset mountpoint is exported rather than simple dir,
    we disable subtree checking as an optimization. This check
    makes sure we're doing this as expected:

    Sample:
    "/mnt/dozer/NFSV4"\
        *(sec=sys,rw,no_subtree_check)
    "/mnt/dozer/NFSV4/foobar"\
        *(sec=sys,rw,subtree_check)
    """
    depends(request, ["pool_04"], scope="session")
    tmp_path = f'{NFS_PATH}/sub1'
    results = POST('/filesystem/mkdir', tmp_path)
    assert results.status_code == 200, results.text

    with nfs_share(tmp_path, {'hosts': ['127.0.0.1']}):
        parsed = parse_exports()
        assert len(parsed) == 2, str(parsed)

        assert parsed[0]['path'] == NFS_PATH, str(parsed)
        assert 'no_subtree_check' in parsed[0]['opts'][0]['parameters'], str(parsed)

        assert parsed[1]['path'] == tmp_path, str(parsed)
        assert 'subtree_check' in parsed[1]['opts'][0]['parameters'], str(parsed)


class Test37WithFixture:
    """
    Wrap a class around test_37 to allow calling the fixture only once
    in the parametrized test
    """

    @pytest.fixture(scope='class')
    def dataset_and_dirs(self):
        """
        Create a dataset and an NFS share for it for host 127.0.0.1 only
        In the dataset, create directories: dir1, dir2, dir3
        In each directory, create subdirs: subdir1, subdir2, subdir3
        """

        vol0 = f'/mnt/{pool_name}/VOL0'
        with nfs_dataset('VOL0'):
            # Top level shared to narrow host
            with nfs_share(vol0, {'hosts': ['127.0.0.1']}):
                # Get the initial list of entries for the cleanup test
                contents = GET('/sharing/nfs').json()
                startIdList = [item.get('id') for item in contents]

                # Create the dirs
                dirs = ["dir1", "dir2", "dir3", "dir4", "dir5", "dir6"]
                subdirs = ["subdir1", "subdir2", "subdir3"]
                try:
                    for dir in dirs:
                        results = SSH_TEST(f"mkdir -p {vol0}/{dir}", user, password, ip)
                        assert results['result'] is True
                        for subdir in subdirs:
                            results = SSH_TEST(f"mkdir -p {vol0}/{dir}/{subdir}", user, password, ip)
                            assert results['result'] is True

                    yield vol0
                finally:
                    # Remove the created dirs
                    for dir in dirs:
                        SSH_TEST(f"rm -rf {vol0}/{dir}", user, password, ip)
                        assert results['result'] is True

                    # Remove the created shares
                    contents = GET('/sharing/nfs').json()
                    endIdList = [item.get('id') for item in contents]
                    for id in endIdList:
                        if id not in startIdList:
                            result = DELETE(f"/sharing/nfs/id/{id}/")
                            assert result.status_code == 200, result.text

    # Parameters for test_37
    # Directory (dataset share VOL0), hostname, ExpectedToPass
    dirs_to_export = [
        ("dir1", ["*"], True),  # Test NAS-120957
        ("dir2", ["*"], True),  # Test NAS-120957, allow non-related paths to same hosts
        ("dir3", ["*.example.com"], True),
        ("dir3", ["*.example.com"], False),  # Already exported
        ("dir1/subdir1", ["192.168.0.0"], True),
        ("dir1/subdir2", ["127.0.0.1"], False),  # Already exported at share root, VOL0
        ("dir4/subdir1", ["192.168.1.0"], True),
        ("dir4", ["192.168.1.0"], False),  # Already shared by dir4/subdir1
        ("dir4", ["*.ixsystems.com"], True),
        ("dir4/subdir2", ["192.168.1.0", "*.ixsystems.com"], False)  # ixsystems already shared
    ]

    @pytest.mark.parametrize("dirname,host,ExpectedToPass", dirs_to_export)
    def test_37_check_nfsdir_subtree_share(self, request, dataset_and_dirs, dirname, host, ExpectedToPass):
        """
        Sharing subtrees to the same host can cause problems for
        NFSv3.  This check makes sure a share creation follows
        the rules.
            * First match is applied
            * A new path that is related to an existing path cannot be shared to same 'host'

        For example, the following is not allowed:
        "/mnt/dozer/NFS"\
            fred(rw)
        "/mnt/dozer/NFS/foo"\
            fred(rw)
        """
        depends(request, ["pool_04", "ssh_password"], scope="session")

        vol = dataset_and_dirs
        dirpath = f'{vol}/{dirname}'
        payload = {"path": dirpath, "hosts": host}
        results = POST("/sharing/nfs/", payload)
        if ExpectedToPass:
            assert results.status_code == 200, results.text
        else:
            assert results.status_code != 200, results.text


def test_38_check_nfs_allow_nonroot_behavior(request):
    """
    If global configuration option "allow_nonroot" is set, then
    we append "insecure" to each exports line.
    Since this is a global option, it triggers an nfsd restart
    even though it's not technically required.

    Sample:
    "/mnt/dozer/NFSV4"\
        *(sec=sys,rw,insecure,no_subtree_check)
    """

    # Verify that NFS server configuration is as expected
    depends(request, ["pool_04"], scope="session")
    results = GET("/nfs")
    assert results.status_code == 200, results.text
    assert results.json()['allow_nonroot'] is False, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    assert 'insecure' not in parsed[0]['opts'][0]['parameters'], str(parsed)

    results = PUT("/nfs/", {"allow_nonroot": True})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    assert 'insecure' in parsed[0]['opts'][0]['parameters'], str(parsed)

    results = PUT("/nfs/", {"allow_nonroot": False})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    assert 'insecure' not in parsed[0]['opts'][0]['parameters'], str(parsed)


def test_39_check_nfs_service_protocols_parameter(request):
    """
    This test verifies that changing the `protocols` option generates expected
    changes in nfs kernel server config.  In most cases we will also confirm
    the settings have taken effect.

    For the time being this test will also exercise the deprecated `v4` option
    to the same effect, but this will later be removed.

    NFS must be enabled for this test to succeed as while the config (i.e.
    database) will be updated regardless, the server config file will not
    be updated.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "RUNNING", results

    # Check existing config (both NFSv3 & NFSv4 configured)
    results = GET("/nfs")
    assert results.status_code == 200, results.text
    protocols = results.json()['protocols']
    assert "NFSV3" in protocols, results.text
    assert "NFSV4" in protocols, results.text

    s = parse_server_config()
    assert s['nfsd']["vers3"] == 'y', str(s)
    assert s['nfsd']["vers4"] == 'y', str(s)

    # Turn off NFSv4 (v3 on)
    results = PUT("/nfs/", {"protocols": ["NFSV3"]})
    assert results.status_code == 200, results.text

    results = GET("/nfs")
    assert results.status_code == 200, results.text
    protocols = results.json()['protocols']
    assert "NFSV3" in protocols, results.text
    assert "NFSV4" not in protocols, results.text

    s = parse_server_config()
    assert s['nfsd']["vers3"] == 'y', str(s)
    assert s['nfsd']["vers4"] == 'n', str(s)

    # Confirm setting has taken effect: v4->off, v3->on
    results = SSH_TEST("rpcinfo -s | grep 100003", user, password, ip)
    assert results['output'].strip().split()[1] == '3', results

    # Try (and fail) to turn off both
    results = PUT("/nfs/", {"protocols": []})
    assert results.status_code != 200, results.text

    # Turn off NFSv3 (v4 on)
    results = PUT("/nfs/", {"protocols": ["NFSV4"]})
    assert results.status_code == 200, results.text

    results = GET("/nfs")
    assert results.status_code == 200, results.text
    protocols = results.json()['protocols']
    assert "NFSV3" not in protocols, results.text
    assert "NFSV4" in protocols, results.text

    s = parse_server_config()
    assert s['nfsd']["vers3"] == 'n', str(s)
    assert s['nfsd']["vers4"] == 'y', str(s)

    # Confirm setting has taken effect: v4->on, v3->off
    results = SSH_TEST("rpcinfo -s | grep 100003", user, password, ip)
    assert results['output'].strip().split()[1] == '4', results

    # Finally turn both back on again
    results = PUT("/nfs/", {"protocols": ["NFSV3", "NFSV4"]})
    assert results.status_code == 200, results.text

    results = GET("/nfs")
    assert results.status_code == 200, results.text
    protocols = results.json()['protocols']
    assert "NFSV3" in protocols, results.text
    assert "NFSV4" in protocols, results.text

    s = parse_server_config()
    assert s['nfsd']["vers3"] == 'y', str(s)
    assert s['nfsd']["vers4"] == 'y', str(s)

    # Confirm setting has taken effect: v4->on, v3->on
    results = SSH_TEST("rpcinfo -s | grep 100003", user, password, ip)
    assert results['output'].strip().split()[1] == '4,3', results


def test_40_check_nfs_service_udp_parameter(request):
    """
    This test verifies that toggling the `udp` option generates expected changes
    in nfs kernel server config.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    with nfs_config():
        get_payload = {'msg': 'method', 'method': 'nfs.config', 'params': []}
        set_payload = {'msg': 'method', 'method': 'nfs.update', 'params': []}

        # Initial state should be disabled:
        #    DB == False, conf == 'n'
        res = make_ws_request(ip, get_payload)
        assert res['result']['udp'] is False, res
        s = parse_server_config()
        assert s['nfsd']["udp"] == 'n', str(s)

        # Multiple restarts cause systemd failures.  Reset the systemd counters.
        svcs_to_reset = "nfs-idmapd nfs-mountd nfs-server rpcbind rpc-statd"
        results = SSH_TEST(f"systemctl reset-failed {svcs_to_reset}", user, password, ip)
        assert results['result'] is True

        # Confirm we can enable:
        #    DB == True, conf =='y', rpc will indicate supported
        set_payload['params'] = [{'udp': True}]
        res = make_ws_request(ip, set_payload)
        assert res['result']['udp'] is True, res
        s = parse_server_config()
        assert s['nfsd']["udp"] == 'y', str(s)
        res = SSH_TEST(f"rpcinfo -T udp {ip} mount", user, password, ip)
        assert "ready and waiting" in res['output'], res

        # Confirm we can disable:
        #    DB == False, conf =='n', rpc will indicate not supported
        set_payload['params'] = [{'udp': False}]
        res = make_ws_request(ip, set_payload)
        assert res['result']['udp'] is False, res
        s = parse_server_config()
        assert s['nfsd']["udp"] == 'n', str(s)
        res = SSH_TEST(f"rpcinfo -T udp {ip} mount", user, password, ip)
        assert "Program not registered" in res['stderr']


def test_41_check_nfs_service_ports(request):
    """
    This test verifies that the custom ports we specified in
    earlier NFS tests are set in the relevant files.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")

    results = GET("/nfs")
    assert results.status_code == 200, results.text
    config = results.json()

    s = parse_server_config()
    assert int(s['mountd']['port']) == config["mountd_port"], str(s)

    assert int(s['statd']['port']) == config["rpcstatd_port"], str(s)
    assert int(s['lockd']['port']) == config["rpclockd_port"], str(s)


def test_42_check_nfs_client_status(request):
    """
    This test checks the function of API endpoints to list NFSv3 and
    NFSv4 clients by performing loopback mounts on the remote TrueNAS
    server and then checking client counts. Due to inherent imprecision
    of counts over NFSv3 protcol (specifically with regard to decrementing
    sessions) we only verify that count is non-zero for NFSv3.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")

    with SSH_NFS(ip, NFS_PATH, vers=3, user=user, password=password, ip=ip):
        results = GET('/nfs/get_nfs3_clients/', payload={
            'query-filters': [],
            'query-options': {'count': True}
        })
        assert results.status_code == 200, results.text
        assert results.json() != 0, results.text

    with SSH_NFS(ip, NFS_PATH, vers=4, user=user, password=password, ip=ip):
        results = GET('/nfs/get_nfs4_clients/', payload={
            'query-filters': [],
            'query-options': {'count': True}
        })
        assert results.status_code == 200, results.text
        assert results.json() == 1, results.text


def test_43_check_nfsv4_acl_support(request):
    """
    This test validates reading and setting NFSv4 ACLs through an NFSv4
    mount in the following manner:
    1) Create and locally mount an NFSv4 share on the TrueNAS server
    2) Iterate through all possible permissions options and set them
       via an NFS client, read back through NFS client, and read resulting
       ACL through the filesystem API.
    3) Repeate same process for each of the supported flags.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    acl_nfs_path = f'/mnt/{pool_name}/test_nfs4_acl'
    test_perms = {
        "READ_DATA": True,
        "WRITE_DATA": True,
        "EXECUTE": True,
        "APPEND_DATA": True,
        "DELETE_CHILD": True,
        "DELETE": True,
        "READ_ATTRIBUTES": True,
        "WRITE_ATTRIBUTES": True,
        "READ_NAMED_ATTRS": True,
        "WRITE_NAMED_ATTRS": True,
        "READ_ACL": True,
        "WRITE_ACL": True,
        "WRITE_OWNER": True,
        "SYNCHRONIZE": True
    }
    test_flags = {
        "FILE_INHERIT": True,
        "DIRECTORY_INHERIT": True,
        "INHERIT_ONLY": False,
        "NO_PROPAGATE_INHERIT": False,
        "INHERITED": False
    }
    theacl = [
        {"tag": "owner@", "id": -1, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
        {"tag": "group@", "id": -1, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
        {"tag": "everyone@", "id": -1, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
        {"tag": "USER", "id": 65534, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
        {"tag": "GROUP", "id": 666, "perms": test_perms.copy(), "flags": test_flags.copy(), "type": "ALLOW"},
    ]
    with nfs_dataset("test_nfs4_acl", {"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}, theacl):
        with nfs_share(acl_nfs_path):
            with SSH_NFS(ip, acl_nfs_path, vers=4, user=user, password=password, ip=ip) as n:
                nfsacl = n.getacl(".")
                for idx, ace in enumerate(nfsacl):
                    assert ace == theacl[idx], str(ace)

                for perm in test_perms.keys():
                    if perm == 'SYNCHRONIZE':
                        # break in SYNCHRONIZE because Linux tool limitation
                        break

                    theacl[4]['perms'][perm] = False
                    n.setacl(".", theacl)
                    nfsacl = n.getacl(".")
                    for idx, ace in enumerate(nfsacl):
                        assert ace == theacl[idx], str(ace)

                    payload = {
                        'path': acl_nfs_path,
                        'simplified': False
                    }
                    result = POST('/filesystem/getacl/', payload)
                    assert result.status_code == 200, result.text

                    for idx, ace in enumerate(result.json()['acl']):
                        assert ace == nfsacl[idx], str(ace)

                for flag in ("INHERIT_ONLY", "NO_PROPAGATE_INHERIT"):
                    theacl[4]['flags'][flag] = True
                    n.setacl(".", theacl)
                    nfsacl = n.getacl(".")
                    for idx, ace in enumerate(nfsacl):
                        assert ace == theacl[idx], str(ace)

                    payload = {
                        'path': acl_nfs_path,
                        'simplified': False
                    }
                    result = POST('/filesystem/getacl/', payload)
                    assert result.status_code == 200, result.text

                    for idx, ace in enumerate(result.json()['acl']):
                        assert ace == nfsacl[idx], str(ace)


def test_44_check_nfs_xattr_support(request):
    """
    Perform basic validation of NFSv4.2 xattr support.
    Mount path via NFS 4.2, create a file and dir,
    and write + read xattr on each.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    xattr_nfs_path = f'/mnt/{pool_name}/test_nfs4_xattr'
    with nfs_dataset("test_nfs4_xattr"):
        with nfs_share(xattr_nfs_path):
            with SSH_NFS(ip, xattr_nfs_path, vers=4.2, user=user, password=password, ip=ip) as n:
                n.create("testfile")
                n.setxattr("testfile", "user.testxattr", "the_contents")
                xattr_val = n.getxattr("testfile", "user.testxattr")
                assert xattr_val == "the_contents"

                n.create("testdir", True)
                n.setxattr("testdir", "user.testxattr2", "the_contents2")
                xattr_val = n.getxattr("testdir", "user.testxattr2")
                assert xattr_val == "the_contents2"


def test_45_check_setting_runtime_debug(request):
    """
    This validates that the private NFS debugging API works correctly.
    """
    depends(request, ["pool_04"], scope="session")
    disabled = {"NFS": ["NONE"], "NFSD": ["NONE"], "NLM": ["NONE"], "RPC": ["NONE"]}
    enabled = {"NFS": ["PROC", "XDR", "CLIENT", "MOUNT", "XATTR_CACHE"],
               "NFSD": ["ALL"],
               "NLM": ["CLIENT", "CLNTLOCK", "SVC"],
               "RPC": ["CALL", "NFS", "TRANS"]}

    try:
        get_payload = {'msg': 'method', 'method': 'nfs.get_debug', 'params': []}
        res = make_ws_request(ip, get_payload)
        assert res['result'] == disabled, res

        set_payload = {'msg': 'method', 'method': 'nfs.set_debug', 'params': [enabled]}
        make_ws_request(ip, set_payload)
        res = make_ws_request(ip, get_payload)
        assert set(res['result']['NFS']) == set(enabled['NFS']), f"Mismatch on NFS: {res}"
        assert set(res['result']['NFSD']) == set(enabled['NFSD']), f"Mismatch on NFSD: {res}"
        assert set(res['result']['NLM']) == set(enabled['NLM']), f"Mismatch on NLM: {res}"
        assert set(res['result']['RPC']) == set(enabled['RPC']), f"Mismatch on RPC: {res}"

    finally:
        set_payload['params'] = [disabled]
        make_ws_request(ip, set_payload)
        res = make_ws_request(ip, get_payload)
        assert res['result'] == disabled, res


def test_50_stoping_nfs_service(request):
    depends(request, ["pool_04"], scope="session")
    # Restore original settings before we stop
    restore_nfs_config()
    payload = {"service": "nfs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_51_checking_to_see_if_nfs_service_is_stop(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "STOPPED", results.text


def test_52_check_adjusting_threadpool_mode(request):
    """
    Verify that NFS thread pool configuration can be adjusted
    through private API endpoints.

    This request will fail if NFS server (or NFS client) is
    still running.
    """
    supported_modes = ["AUTO", "PERCPU", "PERNODE", "GLOBAL"]
    payload = {'msg': 'method', 'method': None, 'params': []}

    for m in supported_modes:
        payload.update({'method': 'nfs.set_threadpool_mode', 'params': [m]})
        make_ws_request(ip, payload)

        payload.update({'method': 'nfs.get_threadpool_mode', 'params': []})
        res = make_ws_request(ip, payload)
        assert res['result'] == m, res


def test_53_set_bind_ip():
    '''
    This test requires a static IP address
    '''
    res = GET("/nfs/bindip_choices")
    assert res.status_code == 200, res.text
    assert ip in res.json(), res.text

    res = PUT("/nfs/", {"bindip": [ip]})
    assert res.status_code == 200, res.text

    # reset to default
    res = PUT("/nfs/", {"bindip": []})
    assert res.status_code == 200, res.text


def test_54_disable_nfs_service_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT("/service/id/nfs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_55_checking_nfs_disable_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]['enable'] is False, results.text


def test_56_destroying_smb_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
