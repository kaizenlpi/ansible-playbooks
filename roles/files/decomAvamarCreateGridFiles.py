# Script will generate files if the grid files are older than 7 days. 
# This ensures avamar clients are added to our output files to be parsed in the next script when a decom avamar emailed payload request passed from ServiceNow comes in.
# host vars were added to a decomAvamar workflow in VRA.

#import pexpect
from genericpath import exists
import paramiko
import xml.etree.ElementTree as ET 
import os
from datetime import datetime,timedelta

# Grids where the VM server's live as a client. In avamar the vm is registered as a client on the avamar grids. 
#AVAMAR GRIDS
avamarGrid1="202.67.16.8"
avamarGrid2="202.67.16.12"
avamarGrid3="202.67.16.32"
avamarGrid4="202.67.16.46"

gridarray=[avmarGrid1,avmarGrid2,avmarGrid3,avmarGrid4] # variable objects inserted here. no need for quotes. 
command = "sudo mccli client show --domain=/ --recursive=true --xml" # ssh command that is run capture grid output as an XML file to easily parse and read. 
gridCount = 0 # start with a counter of 0

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# How the SSH connect is works
#ssh.connect(hostname='202.67.16.8', username='administrator', password='SuperGenericPassword', port=22)
# block - for loop runs to connect to each grid, then runs command and captures output to create a avamar grid file, then makes conncetion to next server to do same process.
for grid in gridarray:
    gridFilename = "/tmp/grid_" + grid + ".xml"
    if os.path.isfile(gridFilename):
        sevenDaysAgo= datetime.now() - timedelta(days=7)
        file_time = datetime.fromtimestamp(os.path.getctime(gridFilename))
        if sevenDaysAgo < file_time: 
            continue         
    gridCount = gridCount + 1
    print("---starting gridname:"+ grid) 
    ssh.connect(hostname=grid, username='administrator', password='SuperGenericPassword')
    stdin, stdout, stderr = ssh.exec_command(command)
    tree=ET.parse(stdout) # 
    root=tree.getroot()
    print(root)
    #lines = stdout.readlines()
    #print(lines)
    lines = stderr.readlines()
    dataNode = tree.find("Data")
    dataNode.set("grid_ip", grid) # grid_ip is an attribute
    tree._setroot(dataNode)
    tree.write(gridFilename)
    #print(dataNode)
    for resultNode in root.findall("Results]"): # removing the <Results> node from the XML output
        root.remove(resultNode)
        #print("in the forloop")   
    #b_xml = tree.tostring()
    #with open("grid_" + grid + ".xml", mode='wb', encoding='utf-8') as out_file:
        #out_file.write(b_xml)
    ssh.close()
    print("---stopping gridname:"+ grid)

if gridCount == 0:
    print("All grid files are current. No new grid files created.")
else: 
    print(gridCount,"grid files created.") 
