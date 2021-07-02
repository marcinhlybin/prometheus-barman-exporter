# Barman exporter for Prometheus

The barman exporter runs `barman` shell command with _experimental_ JSON output. I am the author of JSON output in Barman so it should work fine until somebody else changes output format which may happen in the future.
 
By default `barman-exporter` runs as a service and binds to 127.0.0.1:9780. Metrics are cached and refreshed every hour.

You can run `barman-exporter` from cron using `-f` argument to output results to a textfile:

```
/usr/local/bin/barman-exporter -f /var/lib/prometheus/node_exporter/barman.prom
```

In such case the `node_exporter` must point to this path with `--collector.textfile.directory` option.

## Grafana dashboard

You can find basic grafana dashboard in `grafana-dashboard.json`. It is open for improvements.

![Grafana screenshot](grafana-screenshot.png?raw=true "Grafana screenshot")

## Usage

```
usage: barman-exporter [-h] [-u USER] [-g GROUP] [-m MODE] [-c SECONDS] [-v] [-f TEXTFILE_PATH | -l HOST:PORT | -d]
                       [servers [servers ...]]

Barman exporter

positional arguments:
  servers               Space separated list of servers to check (default: ['all'])

optional arguments:
  -h, --help            show this help message and exit
  -u USER, --user USER  Textfile owner (default: prometheus)
  -g GROUP, --group GROUP
                        Textfile group (default: prometheus)
  -m MODE, --mode MODE  Textfile mode (default: 0644)
  -c SECONDS, --cache-time SECONDS
                        Number of seconds to cache barman output for (default: 3600)
  -v, --version         Show barman exporter version (default: False)
  -f TEXTFILE_PATH, --file TEXTFILE_PATH
                        Save output to textfile (default: None)
  -l HOST:PORT, --listen-address HOST:PORT
                        Address to listen on (default: 127.0.0.1:9780)
  -d, --debug           Print output to stdout (default: False)
```

Examples:

- `$ /usr/local/bin/barman-exporter postgres-01`
- `$ /usr/local/bin/barman-exporter postgres-01 postgres-02`
- `$ /usr/local/bin/barman-exporter all`
- `$ /usr/local/bin/barman-exporter -l 10.10.10.10:9780 -c 900`
- `$ /usr/local/bin/barman-exporter -f /var/lib/prometheus/node_exporter/barman.prom -u prometheus -g prometheus -m 0640 all`

## Requirements

Python3 and following modules are required to run it:

- prometheus_client
- sh

All dependencies will be installed automatically with pip command (see Installation).

## Installation

```
pip3 install barman-exporter
```

### Systemd service file to run barman-exporter as a service

```
[Unit]
Description=Barman Exporter
After=network-online.target

[Service]
Type=simple
User=barman
Group=barman
ExecStart=/usr/local/bin/barman-exporter -l 10.10.10.10:9780 -c 3600
SyslogIdentifier=barman_exporter
Restart=always

[Install]
WantedBy=multi-user.target
```

### Cron job to run barman-exporter with textfile output

If you don't want to use barman exporter as a service you can run it with `-f` argument from the cron job. To run it every hour:

```
0 * * * * /usr/local/bin/barman-exporter -f /var/lib/prometheus/node_exporter/barman.prom
```

In this mode barman exporter does not require any Prometheus configuration because it uses **node-exporter** to parse the metrics from a textfile. Remember to use `--collector.textfile.directory` in `node-exporter` to define a directory with textfiles.

## Prometheus configuration

Please note that `barman-exporter` is listing all backups which is quite heavy operation to perform and it takes some time. Barman exporter caches its results because execution every 5 seconds would be impossible.

```
scrape_configs:
  - job_name: barman
    static_configs:
      - targets:
        - 10.10.10.10:9780'
```

## Metrics

- `number=1` label indicates the newest backup
- `barman_backups_size` and `barman_backup_wal_size` show successful backups only. Failed backups will not be listed here.
- `barman_backups_total` includes failed backups
- `barman_backups_failed`exposes the number of failed backups.
- `barman_last_backup_copy_time` shows how long it takes to make a backup
- `barman_up` shows all checks from `barman check SERVER_NAME` command. Output `OK` is `1.0`, `FAILED` is `0.0`.
- `barman_metrics_update` shows a timestamp when barman metrics has been last updated

With `barman_last_backup` and `barman_first_backup` you can easily calculate when the latest backup was completed:

```
time() - barman_last_backup{instance="$instance", server="$server"}
```

### Raw metrics

```
# HELP barman_backup_size Size of available backups
# TYPE barman_backup_size gauge
barman_backup_size{number="1",server="postgres-01"} 1.429365116108e+012
barman_backup_size{number="2",server="postgres-01"} 1.429365116108e+012
barman_backup_size{number="3",server="postgres-01"} 1.429365116108e+012
barman_backup_size{number="4",server="postgres-01"} 1.429365116108e+012
barman_backup_size{number="5",server="postgres-01"} 1.429365116108e+012
barman_backup_size{number="6",server="postgres-01"} 1.429365116108e+012
barman_backup_size{number="7",server="postgres-01"} 1.429365116108e+012
barman_backup_size{number="8",server="postgres-01"} 1.429365116108e+012

# HELP barman_backup_wal_size WAL size of available backups
# TYPE barman_backup_wal_size gauge
barman_backup_wal_size{number="1",server="postgres-01"} 1.94347270144e+011
barman_backup_wal_size{number="2",server="postgres-01"} 3.06553290752e+011
barman_backup_wal_size{number="3",server="postgres-01"} 3.05479548928e+011
barman_backup_wal_size{number="4",server="postgres-01"} 4.79318350233e+011
barman_backup_wal_size{number="5",server="postgres-01"} 2.87333312102e+011
barman_backup_wal_size{number="6",server="postgres-01"} 2.73267294208e+011
barman_backup_wal_size{number="7",server="postgres-01"} 3.65501716889e+011
barman_backup_wal_size{number="8",server="postgres-01"} 2.34075717632e+011

# HELP barman_backups_total Total number of backups
# TYPE barman_backups_total gauge
barman_backups_total{server="postgres-01"} 9.0

# HELP barman_backups_failed Number of failed backups
# TYPE barman_backups_failed gauge
barman_backups_failed{server="postgres-01"} 1.0

# HELP barman_last_backup Last successful backup timestamp
# TYPE barman_last_backup gauge
barman_last_backup{server="postgres-01"} 1.562537102e+09

# HELP barman_last_backup_copy_time Last successful backup copy time
# TYPE barman_last_backup_copy_time gauge
barman_last_backup_copy_time{server="postgres-01"} 18706.918297

# HELP barman_first_backup First successful backup timestamp
# TYPE barman_first_backup gauge
barman_first_backup{server="postgres-01"} 1.561154701e+09

# HELP barman_up Barman status checks
# TYPE barman_up gauge
barman_up{check="archiver_errors",server="postgres-01"} 1.0
barman_up{check="backup_maximum_age",server="postgres-01"} 1.0
barman_up{check="compression_settings",server="postgres-01"} 1.0
barman_up{check="directories",server="postgres-01"} 1.0
barman_up{check="failed_backups",server="postgres-01"} 1.0
barman_up{check="is_superuser",server="postgres-01"} 1.0
barman_up{check="minimum_redundancy_requirements",server="postgres-01"} 1.0
barman_up{check="pg_basebackup",server="postgres-01"} 1.0
barman_up{check="pg_basebackup_compatible",server="postgres-01"} 1.0
barman_up{check="pg_basebackup_supports_tablespaces_mapping",server="postgres-01"} 1.0
barman_up{check="pg_receivexlog",server="postgres-01"} 1.0
barman_up{check="pg_receivexlog_compatible",server="postgres-01"} 1.0
barman_up{check="postgresql",server="postgres-01"} 1.0
barman_up{check="postgresql_streaming",server="postgres-01"} 1.0
barman_up{check="receive_wal_running",server="postgres-01"} 1.0
barman_up{check="replication_slot",server="postgres-01"} 1.0
barman_up{check="retention_policy_settings",server="postgres-01"} 1.0
barman_up{check="systemid_coherence",server="postgres-01"} 1.0
barman_up{check="wal_level",server="postgres-01"} 1.0

# HELP barman_metrics_update Barman metrics update timestamp
# TYPE barman_metrics_update gauge
barman_metrics_update{server="autouncle"} 1.580485601e+09
```

## Development

Upload to PyPi:

```
source venv/bin/activate
rm -f dist/*
python3 setup.py sdist
twine upload dist/*
```
