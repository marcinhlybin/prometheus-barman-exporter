import os
import sys
import argparse
import time
import json
import shutil
import threading
import logging
import prometheus_client
from prometheus_client import core
from datetime import datetime

import subprocess

BARMAN_EXPORTER_VERSION = '1.0.10'
sys.tracebacklimit = 0

log_file = '/var/log/barman_exporter.log'
format = '%(asctime)s %(funcName)s:%(lineno)d %(process)d:%(thread)d %(message)s'
logging.basicConfig(filename=log_file, filemode='w', level=logging.INFO, format=format)
# logging.basicConfig(level=logging.INFO, format=format)

def barman_cli(*args, **kwargs):
  try:
    newKwargs = dict()
    for k,v in kwargs.items():
      # Remove all sh module options
      if (k[0]!='_'):
        newKwargs[k]=kwargs[k]
      else:
        print(f'remove {k}')
    res = subprocess.run(['barman', *args], capture_output=True, check=False, text=True, timeout=10, **newKwargs)
    logging.info(f'{res}')
    return res.stdout
  except subprocess.CalledProcessError as e:
    logging.error(f'{e.cmd}: {e.returncode}. {e.stdout}. {e.stderr}')
  except Exception as e:
    logging.error(e)

class Barman:

    cache_time = 120

    def __init__(self, cache_time):
        self.check_barman_version()
        Barman.cache_time = cache_time

    def check_barman_version(self):
        barman_version = tuple(int(v) for v in self.version().split('.'))
        if barman_version < (2, 9):
            raise ValueError("Barman version 2.9+ required")

    @staticmethod
    def cli(*args, **kwargs):
        logging.info('barman_cli: ' + ','.join(map(str,args)) + ", ".join(f"{key}={value}" for key, value in kwargs.items()))
        logging.info(f'cache_time: {Barman.cache_time}')
        output = barman_cli('-f', 'json', *args, **kwargs)
        # logging.info(f'output: {output}')
        output = json.loads(str(output))
        return output

    def version(self):
        version = barman_cli('-v', _err_to_out=True).split()
        return version[0]

    def servers(self):
        servers = self.cli('list-server')
        return list(servers.keys())

    def server_status(self, server_name):
        status = self.cli('status', server_name)
        status = {k: v['message'] for k, v in status[server_name].items()}
        return status

    def server_check(self, server_name):
        check = self.cli('check', server_name, _ok_code=[0, 1])
        check = {k: 1 if v['status'] == "OK" else 0 for k,
                 v in check[server_name].items()}
        return check

    def list_backup(self, server_name):
        backups = self.cli('list-backup', server_name)
        backups_done = [backup for backup in backups[server_name]
                        if backup['status'] == 'DONE']
        backups_failed = [
            backup for backup in backups[server_name] if backup['status'] == 'FAILED']
        return backups_done, backups_failed

    def show_backup(self, server_name, backup_id):
        backup = self.cli('show-backup', server_name, backup_id)
        return backup[server_name]

# During construction of this class instance, barman_cli is called.
class BarmanServer:

    def __init__(self, barman, server_name):
        self.barman = barman
        self.name = server_name
        self.status = barman.server_status(server_name)
        self.checks = barman.server_check(server_name)
        self.backups_done, self.backups_failed = barman.list_backup(
            server_name)

    def backup(self, backup_id):
        return self.barman.show_backup(self.name, backup_id)


class BarmanCollector:

    def __init__(self, barman, servers):
        self.barman = barman
        self.servers = servers
        self.collectors = dict(
            barman_backup_size=core.GaugeMetricFamily(
                'barman_backup_size', "Size of available backups",
                labels=['server', 'number']),
            barman_backup_wal_size=core.GaugeMetricFamily(
                'barman_backup_wal_size', "WAL size of available backups",
                labels=['server', 'number']),
            barman_backups_total=core.GaugeMetricFamily(
                "barman_backups_total", "Total number of backups",
                labels=["server"]),
            barman_backups_failed=core.GaugeMetricFamily(
                "barman_backups_failed", "Number of failed backups",
                labels=["server"]),
            barman_last_backup=core.GaugeMetricFamily(
                "barman_last_backup", "Last successful backup timestamp",
                labels=["server"]),
            barman_last_backup_copy_time=core.GaugeMetricFamily(
                "barman_last_backup_copy_time", "Last successful backup copy time",
                labels=["server"]),
            barman_first_backup=core.GaugeMetricFamily(
                "barman_first_backup", "First successful backup timestamp",
                labels=["server"]),
            barman_up=core.GaugeMetricFamily(
                "barman_up", "Barman status checks",
                labels=["server", "check"]),
            barman_metrics_update=core.GaugeMetricFamily(
                "barman_metrics_update", "Barman metrics update timestamp",
                labels=["server"])
        )

    def collect(self):
        for server_name in self.barman_servers():
            barman_server = BarmanServer(self.barman, server_name)
            self.collect_first_backup(barman_server)
            self.collect_last_backup(barman_server)
            self.collect_backups_total(barman_server)
            self.collect_backups_failed(barman_server)
            self.collect_last_backup_copy_time(barman_server)
            self.collect_barman_backup_size(barman_server)
            self.collect_barman_backup_wal_size(barman_server)
            self.collect_barman_up(barman_server)
            self.collect_barman_metrics_update(barman_server)

        for collector in self.collectors.values():
            yield collector

    def barman_servers(self):
        if self.servers[0] == "all":
            return self.barman.servers()
        else:
            return self.servers

    def collect_first_backup(self, barman_server):
        if barman_server.status['first_backup'] and barman_server.status['first_backup'] != 'None':
            first_backup = datetime.strptime(
                barman_server.status['first_backup'], "%Y%m%dT%H%M%S")
            self.collectors['barman_first_backup'].add_metric(
                [barman_server.name], first_backup.strftime("%s"))

    def collect_last_backup(self, barman_server):
        if barman_server.status['last_backup'] and barman_server.status['last_backup'] != 'None':
            last_backup = datetime.strptime(
                barman_server.status['last_backup'], "%Y%m%dT%H%M%S")
            self.collectors['barman_last_backup'].add_metric(
                [barman_server.name], last_backup.strftime("%s"))

    def collect_backups_total(self, barman_server):
        self.collectors['barman_backups_total'].add_metric([barman_server.name], len(
            barman_server.backups_done) + len(barman_server.backups_failed))

    def collect_backups_failed(self, barman_server):
        self.collectors['barman_backups_failed'].add_metric(
            [barman_server.name], len(barman_server.backups_failed))

    def collect_last_backup_copy_time(self, barman_server):
        last_backup_copy_time = 0
        if len(barman_server.backups_done) > 0:
            backup_id = barman_server.backups_done[0]['backup_id']
            last_backup = barman_server.backup(backup_id)
            last_backup_copy_time = last_backup['base_backup_information']['copy_time_seconds']

        self.collectors['barman_last_backup_copy_time'].add_metric(
            [barman_server.name], last_backup_copy_time)

    def collect_barman_backup_size(self, barman_server):
        for number, backup in enumerate(barman_server.backups_done, 1):
            self.collectors['barman_backup_size'].add_metric(
                [barman_server.name, str(number)], backup['size_bytes'])

    def collect_barman_backup_wal_size(self, barman_server):
        for number, backup in enumerate(barman_server.backups_done, 1):
            self.collectors['barman_backup_wal_size'].add_metric(
                [barman_server.name, str(number)], backup['wal_size_bytes'])

    def collect_barman_up(self, barman_server):
        for check_name, check_value in barman_server.checks.items():
            self.collectors['barman_up'].add_metric(
                [barman_server.name, check_name], check_value)

    def collect_barman_metrics_update(self, barman_server):
        self.collectors['barman_metrics_update'].add_metric(
            [barman_server.name], int(time.time()))


class BarmanCollectorCache:
    def __init__(self, barman, servers, cache_time):
        self.barman = barman
        self.servers = servers
        self._collect = []

    def collect_loop(self):
        logging.info("collect_loop----------")
        try:
            barman_collector = BarmanCollector(self.barman, self.servers)
            self._collect = list(barman_collector.collect())
            logging.info("collected data: ", self._collect)
        except Exception as e:
            logging.error("%s: Line %s: %s\n" % (type(e).__name__, e.__traceback__.tb_lineno, str(e)))
            logging.error(e.__traceback__)
        except:
            logging.error("Unexpected error:", sys.exc_info())

    def collect(self):
        return self._collect


def main():
  try:
    args = parse_args()

    if args.version:
        show_version()
    elif args.debug:
        sys.tracebacklimit = 1
        print_metrics_to_stdout(args)
    elif args.file:
        write_metrics_to_file(args)
    else:
        start_exporter_service(args)
  # except Exception as e:
  #     logging.error("%s: Line %s: %s\n" % (type(e).__name__, e.__traceback__.tb_lineno, str(e)))
  except:
      logging.error("Unexpected error:", sys.exc_info())

def parse_args():
    parser = argparse.ArgumentParser(
        description="Barman exporter",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('servers', nargs="*", default=['all'],
                        help="Space separated list of "
                             "servers to check")
    parser.add_argument('-u', '--user', metavar='USER',
                        default='prometheus', help="Textfile owner")
    parser.add_argument('-g', '--group', metavar='GROUP',
                        default='prometheus', help="Textfile group")
    parser.add_argument('-m', '--mode', metavar='MODE',
                        default='0644', help="Textfile mode")
    parser.add_argument('-c', '--cache-time', metavar='SECONDS', type=int,
                        default=3600, help='Number of seconds to cache barman output for')
    parser.add_argument('-v', '--version', action='store_true', 
                        help='Show barman exporter version')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-f', '--file',
                       metavar="TEXTFILE_PATH",
                       help="Save output to textfile")
    group.add_argument('-l', '--listen-address',
                       default='127.0.0.1:9780',
                       metavar="HOST:PORT",
                       help="Address to listen on")
    group.add_argument('-d', '--debug',
                       action='store_true',
                       help="Print output to stdout")

    return parser.parse_args()

# python3 /barman_exporter.py -l 0.0.0.0:9780 -c 10 -d

def show_version():
    print(BARMAN_EXPORTER_VERSION)
    sys.exit(0)


def write_metrics_to_file(args):
    registry = BarmanCollector(Barman(args.cache_time), args.servers)
    prometheus_client.write_to_textfile(args.file, registry)
    shutil.chown(args.file, user=args.user, group=args.group)
    os.chmod(args.file, mode=int(args.mode, 8))


def start_exporter_service(args):
    try:
        addr, port = args.listen_address.split(":")
    except ValueError as e:
        raise ValueError("Incorrect '--listen-address' value: '{}'.".format(
            args.listen_address), "Use HOST:PORT.") from e

    registry = BarmanCollectorCache(Barman(args.cache_time), args.servers, args.cache_time)
    core.REGISTRY.register(registry)

    print("Listening on " + args.listen_address)
    prometheus_client.start_http_server(int(port), addr)

    while True:
        registry.collect_loop()
        time.sleep(args.cache_time)


def print_metrics_to_stdout(args):
    registry = BarmanCollector(Barman(args.cache_time), args.servers)
    print(prometheus_client.generate_latest(registry).decode())


if __name__ == "__main__":
    main()

