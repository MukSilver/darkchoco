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
