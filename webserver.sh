#!/bin/bash

HOME=/home/crmdancer
VENVDIR=$HOME/env/bin
BINDIR=$HOME/thewire

cd $BINDIR
source $VENVDIR/activate
/home/crmdancer/env/bin/gunicorn  -b localhost:8001  main:app 
