# Introduction

This script runs an environment logger system that monitors temperature and light intensity on a Rapsberry Pi Zero W. The script works on a circuit connected as shown below.

![][circuit_diagram.JPG]

# Setup

Follow the below steps to install the relavent dependancies 

```bash

$ sudo apt-get update
$ sudo apt install build-essential python3-dev python3-smbus python3-pip
$ sudo pip3 install adafruit-circuitpython-mcp3xxx

```

Upon installing the dependacies run the script as follows

```bash

$ python3 monitor.py

```
Experiment with circuit and see values change
