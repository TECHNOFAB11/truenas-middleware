import asyncio
import re

import sysctl
RE_ISDISK = re.compile(r'^(da|ada|vtbd|mfid|nvd|pmem)[0-9]+$')


async def added_disk(middleware, disk_name):
    await middleware.call('geom.cache.invalidate')
    await middleware.call('disk.sync', disk_name)
    await middleware.call('disk.sed_unlock', disk_name)
    await middleware.call('disk.multipath_sync')
    await middleware.call('alert.oneshot_delete', 'SMART', disk_name)


async def remove_disk(middleware, disk_name):
    await middleware.call('geom.cache.remove_disk', disk_name)
    await middleware.call('disk.sync', disk_name)
    await middleware.call('disk.multipath_sync')
    await middleware.call('alert.oneshot_delete', 'SMART', disk_name)
    # If a disk dies we need to reconfigure swaps so we are not left
    # with a single disk mirror swap, which may be a point of failure.
    asyncio.ensure_future(middleware.call('disk.swaps_configure'))


async def devd_devfs_hook(middleware, data):
    if data.get('subsystem') != 'CDEV':
        return

    if data['type'] == 'CREATE':
        disks = await middleware.run_in_thread(lambda: sysctl.filter('kern.disks')[0].value.split())
        # Device notified about is not a disk
        if data['cdev'] not in disks:
            return
        await added_disk(middleware, data['cdev'])

    elif data['type'] == 'DESTROY':
        # Device notified about is not a disk
        if not RE_ISDISK.match(data['cdev']):
            return
        await remove_disk(middleware, data['cdev'])


def setup(middleware):
    # Listen to DEVFS events so we can sync on disk attach/detach
    middleware.register_hook('devd.devfs', devd_devfs_hook)
