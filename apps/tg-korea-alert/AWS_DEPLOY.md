# AWS EC2 deployment

This project runs on an Ubuntu EC2 instance as a `systemd` service. The service
starts at boot and restarts after failures.

## Files that must be present on the server

Copy the project to `/home/ubuntu/telegram-monitor`. In addition to the Python
source files, the server needs these local state/secret files:

- `.env`
- `telegram_session.session`
- `alert_monitor.db`

Never commit these files to Git. They are already excluded by `.gitignore`.

`/home/ubuntu/telegram-monitor` must stay a flat copy of this app folder:
`deploy/install_aws_ubuntu.sh` runs `requirements.txt` and
`chmod 600 .env telegram_session.session alert_monitor.db` from that directory,
and `deploy/telegram-monitor.service` starts
`/home/ubuntu/telegram-monitor/korea_alert_monitor.py`. Copying the whole
repository there instead breaks all three. `korea_alert_monitor.py` (the service
itself) needs nothing outside this folder.

The helper scripts do: `check_login.py`, `list_channels.py` and
`collect_messages.py` import `dc_telegram`, which lives in the repository's
top-level `packages/` folder and is resolved from the repository root two
directories above the app folder. They therefore cannot run from the flat
service copy. To use them on the server, place a separate full-repository copy
elsewhere (for example `/home/ubuntu/darkchoco-team`), keeping the
`apps/tg-korea-alert` and `packages/` layout, and run them from
`apps/tg-korea-alert` inside it. Leave the service directory alone.

Before copying the SQLite database, stop the local monitor so its WAL is fully
checkpointed and the database has a consistent snapshot.

## Install

After the files have been copied, connect to the instance and run:

```bash
cd /home/ubuntu/telegram-monitor
chmod +x deploy/install_aws_ubuntu.sh
./deploy/install_aws_ubuntu.sh
```

## Operations

```bash
sudo systemctl status telegram-monitor --no-pager
sudo journalctl -u telegram-monitor -f
sudo systemctl restart telegram-monitor
sudo systemctl stop telegram-monitor
```

The deployment does not require a load balancer, Elastic IP, NAT Gateway, RDS,
or any additional AWS service.
