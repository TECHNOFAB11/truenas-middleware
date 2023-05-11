import time

from middlewared.event import EventSource
from middlewared.schema import Dict, Float, Int
from middlewared.validators import Range

from .ifstat import IfStats


class RealtimeEventSource(EventSource):

    """
    Retrieve real time statistics for CPU, network,
    virtual memory and zfs arc.
    """
    ACCEPTS = Dict(
        Int('interval', default=2, validators=[Range(min=2)]),
    )
    RETURNS = Dict(
        Dict('cpu', additional_attrs=True),
        Dict(
            'disks',
            Float('busy'),
            Float('read_bytes'),
            Float('write_bytes'),
            Float('read_ops'),
            Float('write_ops'),
        ),
        Dict('interfaces', additional_attrs=True),
        Dict(
            'memory',
            Dict(
                'classes',
                Int('apps'),
                Int('arc'),
                Int('buffers'),
                Int('cache'),
                Int('page_tables'),
                Int('slab_cache'),
                Int('swap_cache'),
                Int('unused'),
            ),
            Dict('extra', additional_attrs=True),
            Dict(
                'swap',
                Int('total'),
                Int('used'),
            )
        ),
        Dict('virtual_memory', additional_attrs=True),
        Dict(
            'zfs',
            Int('arc_max_size'),
            Int('arc_size'),
            Float('cache_hit_ratio'),
        ),
    )

    @staticmethod
    def get_cpu_usages(cp_diff):
        cp_total = sum(cp_diff) or 1
        data = {}
        data['user'] = cp_diff[0] / cp_total * 100
        data['nice'] = cp_diff[1] / cp_total * 100
        data['system'] = cp_diff[2] / cp_total * 100
        data['idle'] = cp_diff[3] / cp_total * 100
        data['iowait'] = cp_diff[4] / cp_total * 100
        data['irq'] = cp_diff[5] / cp_total * 100
        data['softirq'] = cp_diff[6] / cp_total * 100
        data['steal'] = cp_diff[7] / cp_total * 100
        data['guest'] = cp_diff[8] / cp_total * 100
        data['guest_nice'] = cp_diff[9] / cp_total * 100
        if sum(cp_diff):
            # Usage is the sum of all but idle and iowait
            data['usage'] = ((cp_total - cp_diff[3] - cp_diff[4]) / cp_total) * 100
        else:
            data['usage'] = 0
        return data

    def run_sync(self):
        interval = self.arg['interval']
        cp_time_last = None
        cp_times_last = None
        last_iface_stats = {}
        internal_interfaces = tuple(self.middleware.call_sync('interface.internal_interfaces'))

        while not self._cancel_sync.is_set():
            data = {}

            # this gathers the most recent metric recorded via netdata (for all charts)
            allmetrics = self.middleware.call_sync('reporting.rest.get_all_metrics')

            # memory info (including zfs arc)
            data.update(self.middleware.call_sync('reporting.memory.info', allmetrics))

            # Get CPU usage %
            data['cpu'] = {}
            num_times = 10
            with open('/proc/stat') as f:
                stat = f.read()
            cp_times = []
            cp_time = []
            for line in stat.split('\n'):
                bits = line.split()
                if bits[0].startswith('cpu'):
                    line_ints = [int(i) for i in bits[1:]]
                    # cpu has a sum of all cpus
                    if bits[0] == 'cpu':
                        cp_time = line_ints
                    # cpuX is for each core
                    else:
                        cp_times += line_ints
                else:
                    break

            if cp_time and cp_times and cp_times_last:
                # Get the difference of times between the last check and the current one
                # cp_time has a list with user, nice, system, interrupt and idle
                cp_diff = list(map(lambda x: x[0] - x[1], zip(cp_times, cp_times_last)))
                cp_nums = int(len(cp_times) / num_times)
                for i in range(cp_nums):
                    data['cpu'][i] = self.get_cpu_usages(cp_diff[i * num_times:i * num_times + num_times])

                cp_diff = list(map(lambda x: x[0] - x[1], zip(cp_time, cp_time_last)))
                data['cpu']['average'] = self.get_cpu_usages(cp_diff)

            cp_time_last = cp_time
            cp_times_last = cp_times

            # CPU temperature
            data['cpu']['temperature_celsius'] = self.middleware.call_sync('reporting.cpu_temperatures')
            data['cpu']['temperature'] = {k: 2732 + int(v * 10) for k, v in data['cpu']['temperature_celsius'].items()}

            # Interface IO Stats
            with IfStats(interval, last_iface_stats, internal_interfaces) as ifstat:
                if not last_iface_stats:
                    # means this is the first time iface stats are being gathered so
                    # get the results but don't set anything yet since we need to
                    # calculate the difference between the iterations
                    last_iface_stats, new = ifstat
                else:
                    last_iface_stats, data['interfaces'] = ifstat

            self.send_event('ADDED', fields=data)
            time.sleep(interval)


def setup(middleware):
    middleware.register_event_source('reporting.realtime', RealtimeEventSource)
