#!/bin/bash

source /PHShome/me741/.bashrc
PATH="$PATH":/usr/share/lsf/9.1/linux2.6-glibc2.3-x86_64
export PATH
export LSF_ENVDIR=/usr/share/lsf/conf
export LSF_SERVERDIR=/usr/share/lsf/9.1/linux2.6-glibc2.3-x86_64/etc

/usr/share/lsf/9.1/linux2.6-glibc2.3-x86_64/bin/bsub < /PHShome/me741/process_audio_diary/extra_utilities/queue_scripts/trans_process_queue.lsf