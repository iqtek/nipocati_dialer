
Debian/ubuntu:

sudo apt-get install python-dev
sudo apt-get install libmysqlclient-dev


CentOS:
sudo yum install python26-devel


python26 virtualenv.py -p python26 py2.6


sudo pip install virtualenv
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt

Install on FreePBX Distro 
===========
yum install python-devel python-twisted-core screen mc yum-protectbase yum-priorities MySQL-python
Add line "check_obsoletes=1" to /etc/yum/pluginconf.d/priorities.conf
Add line "priority=1" to FreePBX.repo in every []
Add line "protect=1" to FreePBX.repo in every []

---Add EPEL for CentOS 6---
rpm -ivh http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm
Add line "priority=2" to epel.repo in [epel]
Install requirements:
yum install ftp://ftp.pbone.net/mirror/ftp5.gwdg.de/pub/opensuse/repositories/home:/tcpip4000:/errepoel/RedHat_RHEL-6/i686/python-basicproperty-0.6.12a-1.1.i686.rpm

---Install Local starpy---
yum install python-pip
cd nipodialer/lib/starpy-master
pip install .

---Add DB and user in MySQL---
CREATE DATABASE asteriskrealtime;
GRANT ALL PRIVILEGES ON asteriskrealtime.* TO 'asteriskuser'@'localhost' IDENTIFIED BY 'youpassword' WITH GRANT OPTION;
flush privileges;
mysql -u asteriskuser -p asteriskrealtime < realtime.sql

Install on Debian:
==========
apt-get install python-dev python-twisted-core screen mc python-starpy python-mysqldb git
wget http://downloads.sourceforge.net/project/basicproperty/basicproperty/0.6.12a/basicproperty-0.6.12a.tar.gz
pip install basicproperty-0.6.12a.tar.gz
cp settings.py.sample settings.py

Todo
==========
1. Reconnect AMI on asterisk restart
2. License code

Notes 
=========
1. The reason for `queue show` on each database modification - AMI QueueStatus give informatio  from emory cache, but not cause updates from mysql.
