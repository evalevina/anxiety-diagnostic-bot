#!/bin/bash
systemctl restart psychologybot
sleep 2
systemctl status psychologybot --no-pager -l
