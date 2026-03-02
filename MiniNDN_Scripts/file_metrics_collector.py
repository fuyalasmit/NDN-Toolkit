# Goes into apps/custom/file_metrics_collector.py
from minindn.apps.application import Application
from mininet.log import debug, info
import time

class NFDMetricsCollector(Application):

    def __init__(self, node, collectionInterval=5, logFolder="./minor_metrics/"):
        Application.__init__(self, node)
        self.collectionInterval = collectionInterval
        self.logFolder = logFolder
        node.cmd('mkdir -p {}'.format(self.logFolder))

    def start(self):
        script_path = f"/tmp/nfd_collector_{self.node.name}.py"
        
        collector_script = f"""#!/usr/bin/env python3
import os
import sys
import time
import json
import signal
import subprocess
from datetime import datetime

def daemonize():
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    os.umask(0)
    if os.fork() > 0:
        sys.exit(0)
    sys.stdout.flush()
    sys.stderr.flush()
    for fd in [sys.stdin, sys.stdout, sys.stderr]:
        devnull = open(os.devnull, 'a+')
        os.dup2(devnull.fileno(), fd.fileno())

def parse_nfd_status(raw):
    result = {{}}
    for line in raw.strip().splitlines():
        line = line.strip()
        if '=' in line:
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            # cast to int where possible
            try:
                result[key] = int(value)
            except ValueError:
                result[key] = value
    return result

def main():
    output_file = '{self.logFolder}/{self.node.name}_metrics.jsonl'
    pid_file = '/tmp/nfd_collector_{self.node.name}.pid'

    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))

    def signal_handler(signum, frame):
        if os.path.exists(pid_file):
            os.remove(pid_file)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    while True:
        try:
            raw = subprocess.check_output(
                ['nfdc', 'status'],
                stderr=subprocess.PIPE,
                timeout=3
            ).decode('utf-8', errors='ignore')

            parsed = parse_nfd_status(raw)

            metrics = {{
                'timestamp': datetime.now().isoformat(),
                'node': '{self.node.name}',
                **parsed
            }}

            with open(output_file, 'a') as f:
                f.write(json.dumps(metrics) + '\\n')
                f.flush()
                os.fsync(f.fileno())

        except Exception as e:
            with open(output_file, 'a') as f:
                f.write(json.dumps({{
                    'timestamp': datetime.now().isoformat(),
                    'node': '{self.node.name}',
                    'error': str(e)
                }}) + '\\n')
                f.flush()

        time.sleep({self.collectionInterval})

if __name__ == '__main__':
    daemonize()
    main()
"""

        with open(script_path, 'w') as f:
            f.write(collector_script)

        self.node.cmd(f"chmod +x {script_path}")
        self.node.cmd(f"python3 {script_path} &")
        time.sleep(0.3)
        info(f"[{self.node.name}] Metrics collector started\n")

    def stop(self):
        pid_file = f"/tmp/nfd_collector_{self.node.name}.pid"
        pid = self.node.cmd(f"cat {pid_file} 2>/dev/null").strip()
        if pid:
            self.node.cmd(f"kill {pid} 2>/dev/null")
            self.node.cmd(f"rm -f {pid_file}")
            debug(f"[{self.node.name}] Stopped metrics collector\n")
