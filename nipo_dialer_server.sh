#!/bin/sh

BASEDIR=$(dirname "$0")


if [ -d "${BASEDIR}/venv" ]; then
    source ${BASEDIR}/venv/bin/activate
    python ${BASEDIR}/nipo_dialer_server.py
    exit
fi
