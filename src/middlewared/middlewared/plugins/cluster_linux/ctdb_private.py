from pathlib import Path

from middlewared.schema import Dict, IPAddr, Int, Bool
from middlewared.service import (accepts, job, filterable,
                                 CRUDService, private, ValidationErrors)
from middlewared.utils import filter_list
from middlewared.plugins.cluster_linux.utils import CTDBConfig


PRI_LOCK = CTDBConfig.PRI_LOCK.value


class CtdbPrivateIpService(CRUDService):

    class Config:
        namespace = 'ctdb.private.ips'
        cli_namespace = 'service.ctdb.private.ips'

    glfs_info = None

    @private
    def contents(self, recursion_cnt=0):
        if not self.glfs_info:
            try:
                info = self.middleware.call_sync('ctdb.shared.volume.info')
                nodes_uuid = self.middleware.call_sync('gluster.filesystem.lookup', {
                    'volume_name': info['volume_name'],
                    'parent_uuid': info['uuid'],
                    'path': CTDBConfig.PRIVATE_IP_FILE.value
                })['uuid']
            except Exception:
                self.logger.debug('Failed to look up ctdb nodes file. Info: %s', info, exc_info=True)
                return []
            else:
                self.glfs_info = {'volume_name': info['volume_name'], 'uuid': nodes_uuid}

        try:
            contents = self.middleware.call_sync('gluster.filesystem.contents', {
                'volume_name': self.glfs_info['volume_name'], 'uuid': self.glfs_info['uuid']
            })
        except Exception:
            self.logger.warning('Failed to read nodes file via uuid: %s', self.glfs_info, exc_info=True)
            if not recursion_cnt:
                self.glfs_info = None
                return self.contents(recursion_cnt + 1)
        else:
            return contents.splitlines()

        return []

    @filterable
    def query(self, filters, options):
        # logic is as follows:
        #   1. if ctdb daemon is started
        #       ctdb just reads the /etc private ip file and loads
        #       the ips written there into the cluster. However,
        #       if a private ip is added/removed, it doesn't
        #       mean the ctdb cluster has been reloaded to
        #       see the changes in the file. So return what
        #       the daemon sees.
        #   2. else
        #       if the ctdb shared volume  is mounted and /etc/ private
        #       ip file exists and is a symlink and the symlink is
        #       pointed to the /cluster private ip file then read it
        #       and return the contents
        ips = []
        if self.middleware.call_sync('service.started', 'ctdb'):
            ips = self.middleware.call_sync('ctdb.general.listnodes')
            ips = list(map(lambda i: dict(i, id=i['pnn']), ips))
        else:
            for idx, i in enumerate(self.contents()):
                ips.append({
                    'id': idx,
                    'pnn': idx,
                    'address': i.split('#')[1] if i.startswith('#') else i,
                    'enabled': not i.startswith('#')
                })

        return filter_list(ips, filters, options)

    @accepts(Dict(
        'private_create',
        IPAddr('ip'),
    ))
    @job(lock=PRI_LOCK)
    async def do_create(self, job, data):
        """
        Add a ctdb private address to the cluster

        `ip` string representing an IP v4/v6 address
        """

        schema_name = 'private_create'
        verrors = ValidationErrors()

        ctdb_volume_info = await self.middleware.call('ctdb.shared.volume.info')
        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data | ctdb_volume_info, schema_name)

        return await self.middleware.call('ctdb.private.ips.query', [('address', '=', data['ip'])])

    @accepts(
        Int('id'),
        Dict(
            'private_update',
            Bool('enable', required=True)
        )
    )
    @job(lock=PRI_LOCK)
    async def do_update(self, job, id, option):
        """
        Update Private IP address from the ctdb cluster with pnn value of `id`.

        `id` integer representing the PNN value for the node.
        `enable` boolean. When True, enable the node else disable the node.
        """

        schema_name = 'private_update'
        verrors = ValidationErrors()

        data = await self.get_instance(id)
        data['enable'] = option['enable']

        ctdb_volume_info = await self.middleware.call('ctdb.shared.volume.info')
        await self.middleware.call('ctdb.ips.common_validation', data, schema_name, verrors)
        await self.middleware.call('ctdb.ips.update_file', data | ctdb_volume_info, schema_name)

        return await self.get_instance(id)
