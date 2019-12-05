import blkid

from middlewared.service import Service, ServiceChangeMixin

from .sync_base import DiskSyncBase


class DiskService(Service, DiskSyncBase, ServiceChangeMixin):

    async def device_to_identifier(self, name):
        disks = await self.middleware.call('device.get_disk')
        if name not in disks:
            return ''
        else:
            block_device = disks[name]

        if block_device['ident']:
            return f'{{serial}}{block_device["ident"]}'
        # FIXME: Verify uuid/label mappings with freebsd version please
        if block_device['uuid']:
            return f'{{uuid}}{block_device["uuid"]}'
        if block_device['label']:
            return f'{{label}}{block_device["label"]}'
        return f'{{devicename}}{name}'

    async def identifier_to_device(self, ident):
        if not ident:
            return None

        search = self.RE_IDENTIFIER.search(ident)
        if not search:
            return None

        tp = search.group('type')
        value = search.group('value')
        mapping = {'uuid': 'uuid', 'label': 'label', 'devicename': 'name', 'serial_lunid': 'ident', 'serial': 'ident'}
        if tp not in mapping:
            raise NotImplementedError(f'Unknown type {tp!r}')

        disk = next(
            (b for b in (await self.middleware.call('device.get_disk')).values() if b[mapping[tp]] == value), None
        )
        return disk['name'] if disk else None

    async def sync_all(self, job):
        raise NotImplementedError()

    async def sync(self, name):
        raise NotImplementedError()
