# The 2nd script that runs in the role to find the VMname server to retire its client on the avamar grid.

from http import server
import paramiko
import xml.etree.ElementTree as ET 
from datetime import datetime, timedelta
import os
import sys
import glob
from itertools import count
from logging import exception
from xml.dom import minidom
import time

# Function: run a MMCLI command on the avamar grid server
def ssh_run_command(ssh_session,command_string):    
    print(command_string)
    stdin, stdout, stderr = ssh_session.exec_command(command_string)
    output = stdout.read()
    result_tree = ET.fromstring(output) # converting output stream into a string
    return_code = result_tree.find('Results/ReturnCode') 
    if return_code.text != '0':
        error_msg = "return code '{3}' event code '{0}' event summary '{1}' command '{2}' "
        event_code = result_tree.find('Results/EventCode') 
        event_summary = result_tree.find('Results/EventSummary') 
        print('ssh_run_command failed - ',error_msg.format(event_code.text,event_summary.text,command_string,return_code.text))
    return result_tree,return_code.text;

# Goal: server_name is required
print(sys.argv[1:])
if len(sys.argv) < 3:
    exception_msg = "usage: {0} [server_name] [finalBackup yes | no] missing correct # of required parameters".format(sys.argv[0]) 
    print(exception_msg)
    raise Exception(exception_msg)
# server_name is the only supported parameter
if len(sys.argv) > 3:
    exception_msg = "usage: {0} [server_name] [finalBackup yes | no] too many parameters".format(sys.argv[0]) 
    print(exception_msg)
    raise Exception(exception_msg)
# set the server_name variable
server_name = sys.argv[1]
finalBackup = sys.argv[2].lower()
if finalBackup not in ["yes","no","true","false"]:
    exception_msg = "usage: {0} [server_name] [finalBackup yes | no] finalBackup was not yes or no".format(sys.argv[0]) 
    print(exception_msg)
    raise Exception(exception_msg)
print('server_name: [' + server_name + ']')

# Goal: Is server_name an Avamar Client
# find avamar clients that exactly matches the server_name in the grid_*.xml files
# for matches extract the (avamar's grid_ip, client_value, domain_value)
print("current_path:",os.getcwd())
grid_list = glob.glob('/tmp/grid_*.xml')
avamar_client_list = []  # create empty array
for grid in grid_list:
    data_tree = ET.parse(grid) # converts the grid file into an xml document
    data_root = data_tree.getroot() 
    # grab attribute from the Data node
    grid_ip = data_root.attrib['grid_ip']
    find_clients = data_root.findall("./Row")
    # loop through all the nodes within the xml file looking for a client_value that matches the server_name
    for node_row in find_clients:
        client_value = node_row.find('Client').text
        domain_value = node_row.find('Domain').text
        if server_name == client_value:
            avamar_client_array = [grid_ip,client_value,domain_value]
            avamar_client_list.append(avamar_client_array)
            print("grid_ip: {0}, client: {1}, domain: {2}".format(grid_ip,client_value,domain_value))# log found clients
# exit if server_name not found in the grid_*.xml files
if len(avamar_client_list) == 0:
    exception_msg = "No Avamar client to retire. server_name [{0}] was not found in the grid_*xml files.".format(server_name) 
    print(exception_msg)
    sys.exit(0) # success no avamar client to retire
# throw exception if more than one client found
if len(avamar_client_list) > 1:
    exception_msg = "Multiple Avamar clients found. server_name [{0}] was found in the grid_*xml files.".format(server_name) 
    print(exception_msg)
    raise Exception(exception_msg)
client_value = ""

# If finalBackup = yes
# Goal: get the list of "Member of Group" (a client can have many) 
group_list = []  # create empty array
if finalBackup in ["yes", "true"]:
    for avamar_client_array in avamar_client_list:
        grid_ip = avamar_client_array[0]
        server_name = avamar_client_array[1]
        domain_value = avamar_client_array[2]
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=grid_ip, username='administrator', password='SuperSecretGenericPassword') 
        group_command = "sudo mccli client show --domain='{0}' --name='{1}' --xml".format(domain_value, server_name)
        activity_tree,return_code = ssh_run_command(ssh,group_command)
        if return_code != '0':
            exception_msg = "Return code is not 0. rc={0}, command={1}".format(return_code,command) 
            print(exception_msg)
            raise Exception(exception_msg)
        row_list = activity_tree.findall('Data/Row')
        # extract all the member of group values for this client
        for row_node in row_list:
            attribute_text = row_node.find('Attribute').text
            value_text = row_node.find('Value').text
            if attribute_text == "Member of Group":
                if "Default" in value_text:
                    print("ignore group {0}, it contains Default.".format(value_text))
                    continue # ignore this row
                # valid group found
                group_array = [grid_ip,server_name,domain_value,value_text]
                group_list.append(group_array)
                print("grid_ip: {0}, server_name: {1}, domain: {2}, group: {3}".format(grid_ip,server_name,domain_value,value_text))
    # throw exception if no valid groups found.
    if len(group_list) == 0: 
        exception_msg = "Did not find any valid backup group. server: {0}".format(server_name)
        print(exception_msg)
        raise Exception(exception_msg)

# If finalBackup = yes   
# Goal: build backup_needed_list. All valid member of groups without a backup within 24 hours.
# for each valid group 
backup_needed_list = []
for group_row in group_list:
    grid_ip = group_row[0]
    server_name = group_row[1]
    domain_value = group_row[2]
    group_value = group_row[3]
    # Goal: Check for completed backup within 24 hours.     
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=grid_ip, username='administrator', password='SuperSecretGenericPassword')
    cuttoff_date = (datetime.now()-timedelta(days=1)) # get today's date and subtract one day
    command = "sudo mccli activity show --domain='{0}' --name='{1}' --verbose=true --xml".format(domain_value,server_name)  
    #command = "sudo mccli activity show --domain='{0}' --name='{1}' --verbose=true --xml".format(domain_value,server_name,cuttoff_date)   
    backup_tree,return_code = ssh_run_command(ssh,command)
    if return_code != '0':
        exception_msg = "Return code is not 0. rc={0}, command={1}".format(return_code,command) 
        print(exception_msg)
        raise Exception(exception_msg)
    row_list = backup_tree.findall('Data/Row')
    # initalize all the vars to empty string
    activity_id = activity_status = activity_group = label_num =  host_name = label = plugin_item = created_data = ""
    valid_backup_found = False
    for row_node in row_list:
        activity_end_time = row_node.find('EndTime').text
        activity_status = row_node.find('Status').text
        activity_id = row_node.find('ID').text
        activity_group = row_node.find('Group').text
        if activity_group == group_value and activity_status == "Completed":
            activity_end_time = activity_end_time[:16] 
            end_time = datetime.strptime(activity_end_time,"%Y-%m-%d %H:%M")
            if cuttoff_date < end_time:
                # found completed backup for group
                valid_backup_found = True
                break  # stop after finding good backup
    # build list of the groups that need a current backup created
    if valid_backup_found == False:
        # save the group row, because it needs a backup to be created.
        backup_needed_array = [grid_ip,server_name,domain_value,group_value,"","backup_activity_id","backup_status"]
        backup_needed_list.append(backup_needed_array)
        print("backup not found for group {0}".format(group_value))
    else:
        # good backup found
        print("good backup found for group {0}, activity ID : {1} Created: {2}".format(group_value,activity_id,activity_end_time))

# If finalBackup = yes
# Goal: start all the backups needed (capture the activity_id)
if len(backup_needed_list) > 0:
    print("Not all backup groups have completed backup")
    for backup_needed_row in backup_needed_list:
        grid_ip = backup_needed_row[0]
        server_name = backup_needed_row[1]
        domain_value = backup_needed_row[2]
        group_value = backup_needed_row[3]
        activity_status = backup_needed_row[4]  
        activity_id = backup_needed_row[5]  
        backup_status = backup_needed_row[6]          
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=grid_ip, username='administrator', password='SuperSecretGenericPassword')        
        # Issue backup command...
        activity_id =""
        backup_command = "sudo mccli client backup-group-dataset --domain='{0}' --name='{1}' --group-name='{2}' --xml".format(domain_value, server_name, group_value)
        activity_tree,return_code = ssh_run_command(ssh,backup_command)
        row_list = activity_tree.findall('Data/Row')
        for row_node in row_list:
                attribute_text = row_node.find('Attribute').text
                value_text = row_node.find('Value').text
                print(attribute_text,value_text)
                if attribute_text == "activity-id":
                    activity_id = value_text 
                    break  # stop when attribute text is activity-id
        if len(activity_id) == 0: # if the activity id is still an empty string, return an exception msg
            backup_needed_row[5] = "failed"
            exception_msg = "The backup command didn't return an activity-id: {0} returncode: {1}".format(backup_command,return_code)
            print(exception_msg)
            raise Exception(exception_msg)
        else:
            backup_needed_row[5] = activity_id

# If finalBackup = yes            
# Goal: wait for all the backups needed to complete (use activity_id)
if len(backup_needed_list) > 0:
    print("waiting for backups for each group have been completed")
    for backup_needed_row in backup_needed_list:
        grid_ip = backup_needed_row[0]
        server_name = backup_needed_row[1]
        domain_value = backup_needed_row[2]
        group_value = backup_needed_row[3]
        activity_status = backup_needed_row[4]  
        activity_id = backup_needed_row[5]  
        backup_status = backup_needed_row[6]          
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=grid_ip, username='administrator', password='SuperSecretGenericPassword')        
        # Issue activity show command...
        activity_show_command = "sudo mccli activity show --id='{0}' --xml".format(activity_id)
        not_completed = 1
        max_loop_count = 24 # 2 hours = 24 loops * 5 min
        loop_count = 0
        while not_completed == 1 and loop_count < max_loop_count: # loop until completed
            loop_count = loop_count + 1
            activity_tree,return_code = ssh_run_command(ssh,activity_show_command)
            row_list = activity_tree.findall('Data/Row')
            for node_row in row_list:
                status_value = node_row.find('Status').text
                if status_value in ['Running','Queued']:
                    backup_needed_row[6] = status_value
                    time.sleep(300)  # 5 min (5*60 sec)
                    break
                if status_value in ['Completed']:
                    backup_needed_row[6] = status_value
                    not_completed = 0
                    print("group: {2} - activity_id: {0} status: {1}".format(activity_id,status_value,group_value))
                    break                       
        if loop_count >= max_loop_count:
            backup_needed_row[6] = "failed"
            exception_msg = "The backup did not complete in the time limit: group: {2} - activity_id: {0} status: {1}".format(activity_id,status_value,group_value)
            print(exception_msg)
            raise Exception(exception_msg)        
        
 
# Goal: retire the avamar client
for avamar_client_array in avamar_client_list:
    grid_ip = avamar_client_array[0]
    server_name = avamar_client_array[1]
    domain_value = avamar_client_array[2]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=grid_ip, username='administrator', password='SuperSecretGenericPassword')
    retire_command = "sudo mccli client retire --domain='{0}' --name='{1}' --xml".format(domain_value,server_name)
    backup_tree,return_code = ssh_run_command(ssh,retire_command)
    if return_code ==0: 
        print(server_name,"client retired")
    if return_code != '0':
        exception_msg = "The retire_command failed. return_code: {0} command: {1}".format(return_code,retire_command)
        print(exception_msg)
        raise Exception(exception_msg)        
