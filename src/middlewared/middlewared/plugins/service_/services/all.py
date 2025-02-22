from .cifs import CIFSService
from .dynamicdns import DynamicDNSService
from .ftp import FTPService
from .haproxy import HAProxyService
from .iscsitarget import ISCSITargetService
from .kuberouter import KubeRouterService
from .kubernetes import KubernetesService
from .mdns import MDNSService
from .netbios import NetBIOSService
from .nfs import NFSService
from .nscd import NSCDService
from .nslcd import NSSPamLdapdService
from .openvpn_client import OpenVPNClientService
from .openvpn_server import OpenVPNServerService
from .rsync import RsyncService
from .smartd import SMARTDService
from .snmp import SNMPService
from .ssh import SSHService
from .truecommand import TruecommandService
from .ups import UPSService
from .webdav import WebDAVService
from .wsd import WSDService
from .keepalived import KeepalivedService
from .glusterd import GlusterdService
from .glustereventsd import GlusterEventsdService
from .ctdb import CtdbService
from .idmap import IdmapService
from .openipmi import OpenIpmiService

from .pseudo.ad import ActiveDirectoryService, LdapService, NisService
from .pseudo.collectd import CollectDService, RRDCacheDService
from .pseudo.libvirtd import LibvirtdService, LibvirtGuestService
from .pseudo.misc import (
    CronService,
    DiskService,
    DSCacheService,
    KmipService,
    LoaderService,
    HostnameService,
    HttpService,
    NetworkService,
    NetworkGeneralService,
    NtpdService,
    OpenVmToolsService,
    PowerdService,
    RcService,
    ResolvConfService,
    RoutingService,
    SslService,
    SyslogdService,
    SystemService,
    TimeservicesService,
    UserService,
)

all_services = [
    CIFSService,
    DSCacheService,
    DynamicDNSService,
    FTPService,
    ISCSITargetService,
    MDNSService,
    NetBIOSService,
    NFSService,
    NSCDService,
    NSSPamLdapdService,
    OpenVPNClientService,
    OpenVPNServerService,
    RsyncService,
    SMARTDService,
    SNMPService,
    SSHService,
    UPSService,
    WebDAVService,
    WSDService,
    ActiveDirectoryService,
    LdapService,
    NisService,
    IdmapService,
    OpenIpmiService,
    KeepalivedService,
    GlusterdService,
    GlusterEventsdService,
    CtdbService,
    KubernetesService,
    KubeRouterService,
    OpenVmToolsService,
    CollectDService,
    RRDCacheDService,
    LibvirtdService,
    LibvirtGuestService,
    CronService,
    DiskService,
    KmipService,
    HAProxyService,
    LoaderService,
    HostnameService,
    HttpService,
    NetworkService,
    NetworkGeneralService,
    NtpdService,
    PowerdService,
    RcService,
    ResolvConfService,
    RoutingService,
    SslService,
    SyslogdService,
    SystemService,
    TimeservicesService,
    TruecommandService,
    UserService,
]
