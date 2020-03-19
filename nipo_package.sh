#!/bin/sh

# Make client package

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 name" >&2
  exit 1
fi

NAME=$1
DATE=`date +%Y-%m-%d`

cp -r ./ ../nipodialer_${DATE}_${NAME}
cd ../nipodialer_${DATE}_${NAME}

rm -rf tests
rm -rf .git
rm -rf py2.7
rm -f *.pyc
rm -f dialer.key
rm -f settings.py
rm -f TODO.md
rm -f nipo_package.sh


