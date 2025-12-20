The following set up does not include any potential changes to be done to the service, timer or config.json files.

Sample setup commands:

```
# general variables
SERVICE_USER=ufaa
EXEC_PATH="/opt/public_ip_poster"
LOG_FILE="/var/log/public_ip_poster.log"
SERVICE_DIR="/etc/systemd/system"

# after cloning the repo, copy folder to EXEC_PATH
sudo cp -R public_ip_poster ${EXEC_PATH}
sudo chown -R ${SERVICE_USER} ${EXEC_PATH}

# create venv
cd ${EXEC_PATH}
python3 -m venv .
source bin/activate
pip3 install -r requirements.txt

# for logging
if [ ! -f $LOG_FILE ]; then sudo touch $LOG_FILE; fi
sudo chown ${SERVICE_USER} ${LOG_FILE}

# set up service and timer files
sudo cp ${EXEC_PATH}/public_ip_poster.service ${EXEC_PATH}/public_ip_poster.timer /etc/systemd/system/
sudo chown ${SERVICE_USER} ${SERVICE_DIR}/public_ip_poster.service
sudo chown ${SERVICE_USER} ${SERVICE_DIR}/public_ip_poster.timer

# start the service
sudo systemctl daemon-reload
sudo systemctl enable public_ip_poster.timer
sudo systemctl start public_ip_poster.timer

# check service and timer status
sudo systemctl list-timers --all
sudo systemctl status public_ip_poster
```

 Uninstall / remove with:

```
EXEC_PATH="/opt/public_ip_poster"
LOG_FILE="/var/log/public_ip_poster.log"
SERVICE_DIR="/etc/systemd/system"

sudo rm -rf ${EXEC_PATH}
sudo rm ${SERVICE_DIR}/public_ip_poster.service
sudo rm ${SERVICE_DIR}/public_ip_poster.timer

# Not strictly necessary
sudo systemctl daemon-reload
sudo rm ${LOG_FILE}
rm -rf ../public
```
