from datetime import timedelta
import logging
import os
import socket

from bsd import getmntinfo
import humanfriendly
import libzfs

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

logger = logging.getLogger(__name__)


class QuotaAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "Quota exceed on dataset"

    schedule = IntervalSchedule(timedelta(minutes=5))

    def check_sync(self):
        alerts = []

        quotas = {}
        for dataset in self.middleware.call_sync("datastore.query", "storage.dataset"):
            quotas[dataset["name"]] = dataset
        quotas[""] = self.middleware.call_sync("datastore.query", "storage.rootdataset", [], {"get": True})

        with libzfs.ZFS() as zfs:
            datasets = [
                {
                    k: v.__getstate__()
                    for k, v in i.properties.items()
                    if k in ["name", "quota", "used", "refquota", "usedbydataset", "mounted", "mountpoint"]
                }
                for i in zfs.datasets
            ]

        for d in datasets:
            d["name"] = d["name"]["rawvalue"]

        datasets = sorted(datasets, key=lambda ds: ds["name"])

        for dataset in datasets:
            for quota_property, used_property in [
                ("quota", "used"),
                ("refquota", "usedbydataset"),
            ]:
                try:
                    quota_value = int(dataset[quota_property]["rawvalue"])
                except (AttributeError, KeyError, ValueError):
                    continue

                if quota_value == 0:
                    continue

                used = int(dataset[used_property]["rawvalue"])
                try:
                    used_fraction = used / quota_value
                except ZeroDivisionError:
                    used_fraction = 1.0

                critical_threshold = self._get_quota(quotas, dataset["name"], f"{quota_property}_critical")
                warning_threshold = self._get_quota(quotas, dataset["name"], f"{quota_property}_warning")
                if critical_threshold != 0 and used_fraction >= critical_threshold:
                    level = AlertLevel.CRITICAL
                elif warning_threshold != 0 and used_fraction >= warning_threshold:
                    level = AlertLevel.WARNING
                else:
                    continue

                quota_name = quota_property[0].upper() + quota_property[1:]

                hostname = socket.gethostname()

                title = ("%(name)s exceed on dataset %(dataset)s. "
                         "Used %(percent_used).2f%% (%(used)s of %(quota_value)s)")
                args = {
                    "name": quota_name,
                    "dataset": dataset["name"],
                    "percent_used": used_fraction * 100,
                    "used": humanfriendly.format_size(used),
                    "quota_value": humanfriendly.format_size(quota_value),
                }

                mail = None
                owner = self._get_owner(dataset)
                if owner != 0:
                    try:
                        bsduser = self.middleware.call_sync(
                            "datastore.query",
                            "account.bsdusers",
                            [["bsdusr_uid", "=", owner]],
                            {"get": True},
                        )
                        to = bsduser["bsdusr_email"] or None
                    except IndexError:
                        logger.debug("Unable to query bsduser with uid %r", owner)
                        to = None

                    if to is not None:
                        mail = {
                            "to": [to],
                            "subject": f"{hostname}: {quota_name} exceed on dataset {dataset['name']}",
                            "text": title % args
                        }

                alerts.append(Alert(
                    title=title,
                    args=args,
                    key=[dataset["name"], quota_property, level.name],
                    level=level,
                    mail=mail,
                ))

        return alerts

    def _get_quota(self, quotas, name, key):
        if name in quotas and quotas[name][key] is not None:
            return quotas[name][key]

        return self._get_quota(quotas, os.path.dirname(name), key)

    def _get_owner(self, dataset):
        mountpoint = None
        if dataset["mounted"]["value"] == "yes":
            if dataset["mountpoint"]["value"] == "legacy":
                for m in getmntinfo():
                    if m.source == dataset["name"]["value"]:
                        mountpoint = m.dest
                        break
            else:
                mountpoint = dataset["mountpoint"]["value"]
        if mountpoint is None:
            logger.debug("Unable to get mountpoint for dataset %r, assuming owner = root", dataset["name"]["value"])
            uid = 0
        else:
            try:
                stat_info = os.stat(mountpoint)
            except Exception:
                logger.debug("Unable to stat mountpoint %r, assuming owner = root", mountpoint)
                uid = 0
            else:
                uid = stat_info.st_uid

        return uid
