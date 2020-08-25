# a shell wrapper to make ansible create a log file with the playbook name and date/time.

#!/bin/bash 
export ANSIBLE_LOG_PATH=/home/myusername/log/$(echo $1 | cut -d . -f 1 && date "+%Y-%m-%d").log 
ansible-playbook $@ 


# Note: In my .bashrc, I added:
# alias ansible-playbook="/home/myusername/ansible-playbook-wrapper.sh"
# Source this file

# Run your playbook to get playbook with date and time. 
# ansible-playbook getcpu_and_mem_lin.yml --extra-vars "target=atinmslx02"
# ls 
# -rw-r--r--  1 myusername osadmin 158124 Aug 25 16:12 getcpu_and_mem_lin?2020-08-25.log

