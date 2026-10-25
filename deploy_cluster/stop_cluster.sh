#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source /home/da/.venvs/quant/bin/activate
python "$DIR/cluster_manager.py" stop
