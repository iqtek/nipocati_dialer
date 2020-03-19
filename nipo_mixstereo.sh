#!/bin/sh

cd /var/spool/asterisk/monitor

sox -M -c 1 $1-r.wav -c 1 $1-t.wav $1-stereo.wav
lame --vbr-new --quiet -V 3 $1.wav $1.mp3
lame --vbr-new --quiet -V 3 $1-stereo.wav $1-stereo.mp3

rm -f $1.wav
rm -f $1-r.wav
rm -f $1-t.wav
rm -f $1-stereo.wav
