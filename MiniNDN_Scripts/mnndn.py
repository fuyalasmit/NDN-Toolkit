# Test simulation
from mininet.log import setLogLevel, info

from minindn.minindn import Minindn
from minindn.util import MiniNDNCLI
from minindn.apps.app_manager import AppManager
from minindn.apps.nfd import Nfd
from minindn.apps.nlsr import Nlsr
from time import sleep

from minindn.apps.custom.file_metrics_collector import NFDMetricsCollector

if __name__ == '__main__':
    setLogLevel('info')

    Minindn.cleanUp()
    Minindn.verifyDependencies()

    ndn = Minindn()

    ndn.start()

    info('Starting NFD on nodes\n')
    nfds = AppManager(ndn, ndn.net.hosts, Nfd)
    info('Starting NLSR on nodes\n')
    nlsrs = AppManager(ndn, ndn.net.hosts, Nlsr)
    sleep(10)

    info('Starting metrics collectors (file mode)\n')
    collectors = AppManager(ndn, ndn.net.hosts, NFDMetricsCollector, 
                           collectionInterval=5,
                           logFolder="./1_minor_metrics/")

    MiniNDNCLI(ndn.net)

    ndn.stop()
