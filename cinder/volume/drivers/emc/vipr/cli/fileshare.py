#!/usr/bin/python

# Copyright (c) 2013 EMC Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import common
import json
import socket
import commands
from common import SOSError
from threading import Timer

class Fileshare(object):
    '''
    The class definition for operations on 'Fileshare'. 
    '''
    #Commonly used URIs for the 'Fileshare' module
    URI_SEARCH_FILESHARES = '/file/filesystems/search?project={0}'
    URI_SEARCH_FILESHARES_BY_PROJECT_AND_NAME='/file/filesystems/search?project={0}&name={1}'
    URI_FILESHARES = '/file/filesystems'
    URI_FILESHARE = URI_FILESHARES + '/{0}'
    URI_FILESHARE_CREATE = URI_FILESHARES + '?project={0}'
    URI_FILESHARE_SNAPSHOTS = URI_FILESHARE + '/snapshots'
    URI_FILESHARE_RESTORE = URI_FILESHARE + '/restore'
    URI_FILESHARE_EXPORTS = URI_FILESHARE + '/exports'
    URI_FILESHARE_SMB_EXPORTS = URI_FILESHARE + '/shares'
    URI_FILESHARE_UNEXPORTS = URI_FILESHARE_EXPORTS + '/{1},{2},{3},{4}'
    URI_FILESHARE_SMB_UNEXPORTS = URI_FILESHARE_SMB_EXPORTS + '/{1}'
    URI_FILESHARE_CONSISTENCYGROUP = URI_FILESHARE + '/consistency-group'
    URI_PROJECT_RESOURCES = '/projects/{0}/resources'
    URI_EXPAND = URI_FILESHARE + '/expand'
    URI_DEACTIVATE = URI_FILESHARE + '/deactivate'
    
    URI_UNMANAGED_FILESYSTEM_INGEST = '/vdc/unmanaged/filesystems/ingest'
    URI_UNMANAGED_FILESYSTEM_SHOW = '/vdc/unmanaged/filesystems/{0}'
    
    URI_TASK_LIST = URI_FILESHARE + '/tasks'
    URI_TASK = URI_TASK_LIST + '/{1}'
    
    isTimeout = False 
    timeout = 300
 
    def __init__(self, ipAddr, port):
        '''
        Constructor: takes IP address and port of the ViPR instance. These are
        needed to make http requests for REST API   
        '''
        self.__ipAddr = ipAddr
        self.__port = port
        
    #Lists fileshares in a project
    def list_fileshares(self, project):
        '''
        Makes REST API call to list fileshares under a project
        Parameters:
            project: name of project
        Returns:
            List of fileshares uuids in JSON response payload
        '''

        from project import Project
        
        proj = Project(self.__ipAddr, self.__port)
        project_uri = proj.project_query(project)
        
        fileshare_uris = self.search_fileshares(project_uri)
        fileshares = []
        for uri in fileshare_uris:
            fileshare = self.show_by_uri(uri)
            if(fileshare):
                fileshares.append(fileshare)
        return fileshares
    
    
    '''
    Given the project name and volume name, the search will be performed to find
    if the fileshare with the given name exists or not. If found, the uri of the fileshare
    will be returned
    '''
    def search_by_project_and_name(self, projectName, fileshareName):
        
        return common.search_by_project_and_name(projectName, fileshareName, Fileshare.URI_SEARCH_FILESHARES_BY_PROJECT_AND_NAME, self.__ipAddr, self.__port) 
    
    
    def search_fileshares(self, project_uri):
        
        (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                              "GET",
                                              Fileshare.URI_SEARCH_FILESHARES.format(project_uri),
                                              None)
        o = common.json_decode(s)
        if not o:
            return []

        fileshare_uris = []
        resources = common.get_node_value(o, "resource")
        for resource in resources:
            fileshare_uris.append(resource["id"])
        return fileshare_uris
    
    #Get the list of fileshares given a project uri    
    def list_by_uri(self, project_uri):
        '''
        Makes REST API call and retrieves fileshares based on project UUID
        Parameters:
            project_uri: UUID of project
        Returns:
            List of fileshare UUIDs in JSON response payload
        '''

        (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                              "GET",
                                              Fileshare.URI_PROJECT_RESOURCES.format(project_uri),
                                              None)
        o = common.json_decode(s)
        if not o:
            return []

        fileshare_uris = []
        resources = common.get_node_value(o, "project_resource")
        for resource in resources:
            if(resource["resource_type"] == "fileshare"):
                fileshare_uris.append(resource["id"])
        return fileshare_uris
    
    # Shows fileshare information given its name
    def show(self, name, show_inactive=False, xml=False):
        '''
        Retrieves fileshare details based on fileshare name
        Parameters:
            name: name of the fileshare. If the fileshare is under a project,
            then full XPath needs to be specified.
            Example: If FS1 is a fileshare under project PROJ1, then the name
            of fileshare is PROJ1/FS1
        Returns:
            Fileshare details in JSON response payload
        '''

        from project import Project

        if (common.is_uri(name)):
            return name

        (pname, label) = common.get_parent_child_from_xpath(name)
        if(not pname):
            raise SOSError(SOSError.NOT_FOUND_ERR,
               "Filesystem " + name + ": not found")
        
        proj = Project(self.__ipAddr, self.__port)
        puri = proj.project_query(pname)

        puri = puri.strip()
        uris = self.search_fileshares(puri)
        
        for uri in uris:
            fileshare = self.show_by_uri(uri, show_inactive)
            if (fileshare and fileshare['name'] == label):
                if(not xml):
                    return fileshare
                else:
                    return self.show_by_uri(fileshare['id'], show_inactive, xml)
        raise SOSError(SOSError.NOT_FOUND_ERR,
                        "Filesystem " + label + ": not found")
    
    # Shows fileshare information given its uri
    def show_by_uri(self, uri, show_inactive=False, xml=False):
        '''
        Makes REST API call and retrieves fileshare details based on UUID
        Parameters:
            uri: UUID of fileshare
        Returns:
            Fileshare details in JSON response payload
        '''
        if(xml):
            (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                             "GET",
                                             Fileshare.URI_FILESHARE.format(uri),
                                             None, None, xml)
            return s
            
        (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                             "GET",
                                             Fileshare.URI_FILESHARE.format(uri),
                                             None)
        if(not s):
            return None
        o = common.json_decode(s)
        if(show_inactive):
            return o
        if('inactive' in o):
            if(o['inactive'] == True):
                return None
        return o

    def unmanaged_filesystem_ingest(self, tenant, project,
                                varray, vpool, filesystems):
        '''
        This function is to ingest given unmanaged filesystems
        into ViPR.
        '''
        from project import Project
        proj_obj = Project(self.__ipAddr, self.__port)
        project_uri = proj_obj.project_query(tenant + "/" + project)

        from virtualpool import VirtualPool
        vpool_obj = VirtualPool(self.__ipAddr, self.__port)
        vpool_uri = vpool_obj.vpool_query(vpool, "file")

        from virtualarray import VirtualArray
        varray_obj = VirtualArray(self.__ipAddr, self.__port)
        varray_uri = varray_obj.varray_query(varray)

        request = {
             'vpool' : vpool_uri,
             'varray' : varray_uri,
             'project' : project_uri,
             'unmanaged_filesystem_list' : filesystems
            }

        body = json.dumps(request)
        (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                             "POST",
                                             Fileshare.URI_UNMANAGED_FILESYSTEM_INGEST,
                                             body)
        o = common.json_decode(s)
        return o

    def unmanaged_filesystem_show(self, filesystem):
        '''
        This function is to show the details of unmanaged filesystem
        from  ViPR.
        '''
        (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                             "GET",
                                             Fileshare.URI_UNMANAGED_FILESYSTEM_SHOW.format(filesystem),
                                             None)
        o = common.json_decode(s)
        return o
    
    # Creates a fileshare given label, project, vpool and size
    def create(self, project, label, size, varray, vpool, protocol, sync):
        '''
        Makes REST API call to create fileshare under a project
        Parameters:
            project: name of the project under which the fileshare will be created
            label: name of fileshare
            size: size of fileshare
            varray: name of varray
            vpool: name of vpool
            protocol: NFS, NFSv4, CIFS 
        Returns:
            Created task details in JSON response payload
        '''

        from virtualpool import VirtualPool
        from project import Project
        from virtualarray import VirtualArray

        vpool_obj = VirtualPool(self.__ipAddr, self.__port)
        vpool_uri = vpool_obj.vpool_query(vpool, "file")
        
        varray_obj = VirtualArray(self.__ipAddr, self.__port)
        varray_uri = varray_obj.varray_query(varray)
        
                    
        parms = {
         'name' : label,
         'size' : size,
         'varray' : varray_uri,
         'vpool' : vpool_uri
         }
      
        if(protocol): 
            parms["protocols"] = protocol
    
        body = json.dumps(parms)

        proj = Project(self.__ipAddr, self.__port)
        project_uri = proj.project_query(project)
        
        try:
            (s, h) = common.service_json_request(self.__ipAddr, self.__port, "POST",
                                             Fileshare.URI_FILESHARE_CREATE.format(project_uri),
                                             body)
            o = common.json_decode(s)
            if(sync):
                #fileshare = self.show(name, True)
                return self.block_until_complete(o["resource"]["id"],
                                             o["op_id"])
            else:
                return o
        except SOSError as e:
                errorMessage = str(e).replace(vpool_uri, vpool)
                errorMessage = errorMessage.replace(varray_uri, varray)
                common.format_err_msg_and_raise("create", "filesystem", errorMessage, e.err_code)
                
             
        



    # Update a fileshare information
    def update(self, name, label, vpool):
        '''
        Makes REST API call to update a fileshare information
        Parameters:
            name: name of the fileshare to be updated
            label: new name of the fileshare
            vpool: name of vpool
        Returns
            Created task details in JSON response payload
        '''
        fileshare_uri = self.fileshare_query(name)
        
        from virtualpool import VirtualPool
        
        vpool_obj = VirtualPool(self.__ipAddr, self.__port)
        vpool_uri = vpool_obj.vpool_query(vpool, "file")
        
        body = json.dumps({'share':
        {
         'label' : label,
         'vpool' : { "id" : vpool_uri }
        }
        })
        
        (s, h) = common.service_json_request(self.__ipAddr, self.__port, "PUT",
                                             Fileshare.URI_FILESHARE.format(fileshare_uri), body)
        o = common.json_decode(s)
        return o
    
    # Exports a fileshare to a host given a fileshare name and the host name
    def export(self, name, security_type, permission, root_user, endpoints, protocol,
               share_name, share_description, permission_type, sub_dir, sync):
        '''
        Makes REST API call to export fileshare to a host
        Parameters:
            name: name of fileshare
            type: type of security
            permission: Permissions
            root_user: root user
            endpoints: host names, IP addresses, or netgroups
            protocol:  NFS, NFSv4, CIFS
            share_name: Name of the SMB share
            share_description: Description of SMB share
        Returns:
            Created Operation ID details in JSON response payload
        '''
        fileshare_uri = name
        try:
            fileshare_uri = self.fileshare_query(name)
            if(protocol == 'CIFS'):
                request = {
                'name'   : share_name,
                'description'   : share_description
                }
            
                if(permission_type):
                     request["permission_type"] = permission_type
                if(permission and permission in ["read", "change", "full"]):
                    request["permission"] = permission
            
                body = json.dumps(request)

           
                (s, h) = common.service_json_request(self.__ipAddr, self.__port, "POST",
                                             Fileshare.URI_FILESHARE_SMB_EXPORTS.format(fileshare_uri),
                                             body)
    
            else:
                request = {
                'type'   : security_type,
                'permissions'   : permission,
                'root_user' : root_user,
                'endpoints' :  endpoints ,
                'protocol' : protocol,
                }
                if(sub_dir):
                    request["sub_directory"] = sub_dir
            
                body = json.dumps(request)
                (s, h) = common.service_json_request(self.__ipAddr, self.__port, "POST",
                                             Fileshare.URI_FILESHARE_EXPORTS.format(fileshare_uri),
                                             body)
            if(not s):
                return None
            o = common.json_decode(s)
            if(sync):
                return self.block_until_complete(fileshare_uri, o["op_id"])
            else:
                return o
        except SOSError as e:
                errorMessage = str(e)
                if(common.is_uri(fileshare_uri)):
                    errorMessage = str(e).replace(fileshare_uri, name)
                common.format_err_msg_and_raise("export", "filesystem", errorMessage, e.err_code)
            
    
    # Unexports a fileshare from a host given a fileshare name, type of security and permission
    def unexport(self, name, security_type, permission, root_user, protocol, share_name, sub_dir, sync):
        '''
        Makes REST API call to unexport fileshare from a host
        Parameters:
            name: name of fileshare
            security_type: type of security
            permission: Permissions
            root_user: root_user mapping
            protocol: NFS, NFSv4, CIFS
        Returns:
            Created Operation ID details in JSON response payload
        '''

        fileshare_uri = self.fileshare_query(name)
        if(protocol == 'CIFS'):
            (s, h) = common.service_json_request(self.__ipAddr, self.__port, "DELETE",
                                             Fileshare.URI_FILESHARE_SMB_UNEXPORTS.format(fileshare_uri, share_name),
                                             None)
        else:
            request_uri = Fileshare.URI_FILESHARE_UNEXPORTS.format(fileshare_uri, protocol,
                                                    security_type, permission, root_user)
            if(sub_dir):
                request_uri = request_uri + "?subDirectory=" + sub_dir
            (s, h) = common.service_json_request(self.__ipAddr, self.__port, "DELETE",
                                                 request_uri, None)
        if(not s):
            return None
        o = common.json_decode(s)
        if(sync):
            return self.block_until_complete(fileshare_uri, o["op_id"])
        else:
            return o
    
    # Deletes a fileshare given a fileshare name
    def delete(self, name, forceDelete=False, sync=False):
        '''
        Deletes a fileshare based on fileshare name
        Parameters:
            name: name of fileshare
        '''
        fileshare_uri = self.fileshare_query(name)
        return self.delete_by_uri(fileshare_uri, forceDelete, sync)
    
    # Deletes a fileshare given a fileshare uri
    def delete_by_uri(self, uri, forceDelete=False, sync=False):
        '''
        Deletes a fileshare based on fileshare uri
        Parameters:
            uri: uri of fileshare
        '''
        request = {"forceDelete":forceDelete}
        body = json.dumps(request)
        (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                             "POST",
                                             Fileshare.URI_DEACTIVATE.format(uri),
                                             body)
        if(not s):
            return None
        o = common.json_decode(s)
        if(sync):
            return self.block_until_complete(o["resource"]["id"], o["op_id"])
        return o
    
    def get_exports_by_uri(self, uri):
        '''
        Get a fileshare export based on fileshare uri
        Parameters:
            uri: uri of fileshare
        '''
        (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                             "GET",
                                             Fileshare.URI_FILESHARE_EXPORTS.format(uri),
                                             None)
        if(not s):
            return None
        o = common.json_decode(s)
        if(not o):
            return None
        return o
    
    def get_exports(self, name):
        '''
        Get a fileshare export based on fileshare name
        Parameters:
            name: name of fileshare
        '''
        fileshare_uri = self.fileshare_query(name)
        return self.get_exports_by_uri(fileshare_uri);
       

    # Queries a fileshare given its name
    def fileshare_query(self, name):
        '''
        Makes REST API call to query the fileshare by name
        Parameters:
            name: name of fileshare
        Returns:
            Fileshare details in JSON response payload
        '''

        from project import Project
        if (common.is_uri(name)):
            return name
        (pname, label) = common.get_parent_child_from_xpath(name)
        if(not pname):
            raise SOSError(SOSError.NOT_FOUND_ERR,
                           "Project name  not specified")

        proj = Project(self.__ipAddr, self.__port)
        puri = proj.project_query(pname)
        puri = puri.strip()
        uris = self.search_fileshares(puri)
        for uri in uris:
            fileshare = self.show_by_uri(uri)
            if (fileshare and fileshare['name'] == label):
                return fileshare['id']
        raise SOSError(SOSError.NOT_FOUND_ERR,
                       "Filesystem " + label + ": not found")

    # Mounts the fileshare to the mount_dir
    def mount(self, name, mount_dir):
        '''
        First we need to export the fileshare to the current machine
        Then we need to find the mount path
        then we need to mount the fileshare to the specified directory
        '''
               
        #share = self.show(name)
        fsExportInfo = self.get_exports(name)
        if(fsExportInfo and "filesystem_export" in fsExportInfo and 
           len(fsExportInfo["filesystem_export"]) > 0):
            fsExport = fsExportInfo["filesystem_export"][0];
            
       
            mount_point = fsExport["mount_point"]
            mount_cmd = 'mount ' + mount_point + " " + mount_dir
                    
            (o, h) = commands.getstatusoutput(mount_cmd)
            if(o == 0):
                return "Filesystem: " + name + " mounted to " + mount_dir + " successfully"
            raise SOSError(SOSError.CMD_LINE_ERR,
                        "Unable to mount " + name + " to " + mount_dir + "\nRoot cause: " + h)
        else:
            raise SOSError(SOSError.NOT_FOUND_ERR,
                       "error: Filesystem: " + name + " is not exported. Export it first.")

    # Timeout handler for synchronous operations
    def timeout_handler(self):
        self.isTimeout = True


    # Blocks the opertaion until the task is complete/error out/timeout
    def block_until_complete(self, resource_uri, op_id):
        self.isTimeout = False 
        t = Timer(self.timeout, self.timeout_handler)
        t.start()
        while(True):
            #out = self.show_by_uri(id)
            out = self.show_task_by_uri(resource_uri, op_id)
            
            if(out):
                if(out["state"] == "ready"):
                    # cancel the timer and return
                    t.cancel()
                    break
                # if the status of the task is 'error' then cancel the timer and raise exception
                if(out["state"] == "error"):
                    # cancel the timer
                    t.cancel()
                    raise SOSError(SOSError.VALUE_ERR,
                                   "Task: " + op_id + " is in ERROR state")

            if(self.isTimeout):
                print "Operation timed out"
                self.isTimeout = False
                break
        return
    
    def list_tasks(self, project_name, fileshare_name=None, task_id=None):
        
        from project import Project
        proj = Project(self.__ipAddr, self.__port)
        puri = proj.project_query(project_name)
        puri = puri.strip()
        uris = self.search_fileshares(puri)
            
        if(fileshare_name):
            for uri in uris:
                fileshare = self.show_by_uri(uri, True)
                if(fileshare['name'] == fileshare_name):
                    if(not task_id):
                        return self.show_task_by_uri(fileshare["id"])
                        
                    else:
                        res = self.show_task_by_uri(fileshare["id"], task_id)
                        if(res):
                            return res
            raise SOSError(SOSError.NOT_FOUND_ERR, "Filesystem with name: " + fileshare_name + " not found")
        else:
            # volume_name is not given, get all tasks
            all_tasks = []
            for uri in uris:
                res = self.show_task_by_uri(uri)
                if(res and len(res) > 0):
                    all_tasks += res
            return all_tasks
            
    def show_task_by_uri(self, volume_uri, task_id=None):
        
        if(not task_id):
            (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                                "GET",
                                                Fileshare.URI_TASK_LIST.format(volume_uri),
                                                None)
            if (not s):
                return []
            o = common.json_decode(s)
            res = o["task"]
            return res
        else:
            (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                                 "GET",
                                                 Fileshare.URI_TASK.format(volume_uri, task_id),
                                                 None)
            if (not s):
                return None
            o = common.json_decode(s)
            return o
    
    def expand(self, name, new_size, sync=False):
        
        fileshare_detail = self.show(name)
        current_size = float(fileshare_detail["capacity_gb"])
        
        if(new_size <= current_size):
            raise SOSError(SOSError.VALUE_ERR,
                           "error: Incorrect value of new size: " + str(new_size) + 
                           " bytes\nNew size must be greater than current size: " + str(current_size) + " bytes")
        
        body = json.dumps({
                           "new_size" : new_size
                           })
        
        (s, h) = common.service_json_request(self.__ipAddr, self.__port,
                                                 "POST",
                                                 Fileshare.URI_EXPAND.format(fileshare_detail["id"]),
                                                 body)
        if(not s):
            return None
        o = common.json_decode(s)
        if(sync):
            return self.block_until_complete(fileshare_detail["id"], o["op_id"])
        return o

# Fileshare Create routines

def create_parser(subcommand_parsers, common_parser):
    create_parser = subcommand_parsers.add_parser('create',
                                description='ViPR Filesystem Create CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Create a filesystem')
    mandatory_args = create_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-name', '-n',
                        metavar='<filesystemname>',
                                dest='name',
                                help='Name of Filesystem',
                                required=True)
    mandatory_args.add_argument('-size', '-s',
                                help='Size of filesystem: {number}[unit]. ' + 
                                'A size suffix of K for kilobytes, M for megabytes, G for  gigabytes, T  for ' + 
                                'terabytes is optional.' + 
                                'Default unit is bytes.',
                                metavar='<filesharesize[kKmMgGtT]>',
                                dest='size',
                                required=True)
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of Project',
                                required=True)
    create_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-vpool', '-vp',
                                metavar='<vpoolname>', dest='vpool',
                                help='Name of vpool',
                                required=True)
    mandatory_args.add_argument('-varray', '-va',
                                help='Name of varray',
                                metavar='<varray>',
                                dest='varray',
                                required=True)
    create_parser.add_argument('-synchronous', '-sync',
                                dest='sync',
                                help='Execute in synchronous mode',
                                action='store_true') 
    create_parser.set_defaults(func=fileshare_create)

def fileshare_create(args):
    
    size = common.to_bytes(args.size)
    if not size:
        raise SOSError(SOSError.CMD_LINE_ERR,
                       'error: Invalid input for -size')
    if(not args.tenant):
        args.tenant = ""
    try:
        obj = Fileshare(args.ip, args.port)
        res = obj.create(args.tenant + "/" + args.project,
                                args.name,
                                size,
                                args.varray,
                                args.vpool,
                                None,
                                args.sync)
#        if(args.sync == False):
#            return common.format_json_object(res)
    except SOSError as e:
        if (e.err_code in [SOSError.NOT_FOUND_ERR,
                           SOSError.ENTRY_ALREADY_EXISTS_ERR]):
            raise SOSError(e.err_code, "Create failed: " + e.err_text)
        else:
            raise e
        
# fileshare Update routines

def update_parser(subcommand_parsers, common_parser):
    update_parser = subcommand_parsers.add_parser('update',
                                description='ViPR Filesystem Update CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Update a filesystem')
    mandatory_args = update_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-name', '-n',
                                help='Name of filesystem',
                                metavar='<filesystemname>',
                                dest='name',
                                required=True)
    update_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of project',
                                required=True)
    mandatory_args.add_argument('-label', '-l',
                                help='New label of filesystem',
                                metavar='<label>',
                                dest='label',
                                required=True)
    mandatory_args.add_argument('-vpool', '-vp',
                                help='Name of New vpool',
                                metavar='<vpoolname>',
                                dest='vpool',
                                required=True)
    
    update_parser.set_defaults(func=fileshare_update)
    

def fileshare_update(args):
    if(not args.tenant):
        args.tenant = ""
    
    try:
        obj = Fileshare(args.ip, args.port)
        res = obj.update(args.tenant + "/" + args.project + "/" + args.name,
                                args.label,
                                args.vpool)
    except SOSError as e:
        if (e.err_code == SOSError.NOT_FOUND_ERR):
            raise SOSError(e.err_code, "Update failed: " + e.err_text)
        else:
            raise e


# Fileshare Delete routines
 
def delete_parser(subcommand_parsers, common_parser):
    delete_parser = subcommand_parsers.add_parser('delete',
                                description='ViPR Filesystem Delete CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Delete a filesystem')
    mandatory_args = delete_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-name', '-n',
                                metavar='<filesystemname>',
                                dest='name',
                                help='Name of Filesystem',
                                required=True)
    delete_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of project',
                                required=True)
    delete_parser.add_argument('-synchronous', '-sync',
                                dest='sync',
                                help='Execute in synchronous mode',
                                action='store_true')
    delete_parser.add_argument('-forceDelete', '-fd',
                                metavar='<forceDelete>',
                                dest='forceDelete',
                                help='Delete fileshare forecibly, default false',
                                default=False)
    delete_parser.set_defaults(func=fileshare_delete)

def fileshare_delete(args):
    if(not args.tenant):
        args.tenant = ""
    obj = Fileshare(args.ip, args.port)
    try:
        obj.delete(args.tenant + "/" + args.project + "/" + args.name, args.forceDelete, args.sync)
    except SOSError as e:
        common.format_err_msg_and_raise("delete", "filesystem", e.err_text, e.err_code)

# Fileshare Export routines

def export_parser(subcommand_parsers, common_parser):
    export_parser = subcommand_parsers.add_parser('export',
                                description='ViPR Filesystem Export CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Export a filesystem')
    mandatory_args = export_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-name', '-n',
                                dest='name',
                                metavar='<filesystemname>',
                                help='Name of Filesystem',
                                required=True)
    export_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of project',
                                required=True)
    export_parser.add_argument('-security', '-sec',
                               metavar='<security>',
                                dest='security',
                                help='Security type')
    export_parser.add_argument('-permission', '-pe',
                                metavar='<permission>',
                                dest='permission',
                                help='Permission')
    export_parser.add_argument('-rootuser', '-ru',
                                metavar='<root_user>',
                                dest='root_user',
                                help='root user')
    export_parser.add_argument('-endpoint', '-e',
                                metavar='<endpoint>',
                                dest='endpoint',
                                nargs='+',
                                help='Endpoints: host names, IP addresses, or netgroups')
    mandatory_args.add_argument('-protocol', '-pl',
                                help='Protocol',
                                choices=["NFS", "NFSv4", "CIFS"],
                                dest='protocol',
                                required=True)
    export_parser.add_argument('-share', '-sh',
                                help='Name of SMB share',
                                dest='share')
    export_parser.add_argument('-description', '-desc',
                                help='Description of SMB share',
                                dest='desc')
    export_parser.add_argument('-permission_type', '-pt',
                               choices=['allow', 'deny'],
                                help='Type of permission of SMB share',
                                dest='permission_type')
    export_parser.add_argument('-subdir',
                                metavar="<sub directory>",
                                help='Export to FileSystem subdirectory',
                                dest='subdir')
    export_parser.add_argument('-synchronous', '-sync',
                                dest='sync',
                                help='Execute in synchronous mode',
                                action='store_true')
    export_parser.set_defaults(func=fileshare_export)

     
def fileshare_export(args):
    
    try:
        if(args.protocol == "CIFS"):
            if(args.share == None):
                raise SOSError(SOSError.CMD_LINE_ERR,
                               'error: -share is required for CIFS export')
            if(args.desc == None):
                raise SOSError(SOSError.CMD_LINE_ERR,
                               'error: -description is required for CIFS export')
        else:
            
            if(args.security == None):
                raise SOSError(SOSError.CMD_LINE_ERR,
                               'error: -security is required for ' + args.protocol + ' export')
            if(args.permission == None):
                raise SOSError(SOSError.CMD_LINE_ERR,
                               'error: -permission is required for ' + args.protocol + ' export')
            if(args.root_user == None):
                raise SOSError(SOSError.CMD_LINE_ERR,
                               'error: -rootuser is required for ' + args.protocol + ' export')
            if(args.endpoint == None):
                raise SOSError(SOSError.CMD_LINE_ERR,
                               'error: -endpoint is required for ' + args.protocol + ' export')


        if(not args.tenant):
            args.tenant = ""
        obj = Fileshare(args.ip, args.port)
        res = obj.export(args.tenant + "/" + args.project + "/" + args.name,
                         args.security, args.permission, args.root_user, args.endpoint,
                         args.protocol, args.share, args.desc, args.permission_type, args.subdir, args.sync)
        
#        if(args.sync == False):
#            return common.format_json_object(res)

    except SOSError as e:
        if (e.err_code == SOSError.NOT_FOUND_ERR):
            raise SOSError(e.err_code, "Export failed: " + e.err_text)
        else:
            raise e
            

# Fileshare UnExport routines

def unexport_parser(subcommand_parsers, common_parser):
    unexport_parser = subcommand_parsers.add_parser('unexport',
                                description='ViPR Filesystem Unexport CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Unexport a filesystem')
    mandatory_args = unexport_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-name', '-n',
                                dest='name',
                                metavar='<filesystemname>',
                                help='Name of Filesystem',
                                required=True)
    unexport_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of project',
                                required=True)
    unexport_parser.add_argument('-security', '-sec',
                                metavar='<security>',
                                dest='security',
                                help='Security type')
    unexport_parser.add_argument('-permission', '-pe',
                                metavar='<permission>',
                                dest='permission',
                                help='Permission')
    unexport_parser.add_argument('-rootuser', '-ru',
                                metavar='<root_user>',
                                dest='root_user',
                                help='root user')
    mandatory_args.add_argument('-protocol', '-pl',
                                help='Protocol',
                                choices=["NFS", "NFSv4", "CIFS"],
                                dest='protocol',
                                required=True)
    unexport_parser.add_argument('-share', '-sh',
                                help='Name of SMB share',
                                dest='share')
    unexport_parser.add_argument('-subdir',
                                metavar="<sub directory>",
                                help='Unexport from FileSystem subdirectory',
                                dest='subdir')
    unexport_parser.add_argument('-synchronous', '-sync',
                                dest='sync',
                                help='Execute in synchronous mode',
                                action='store_true')
    unexport_parser.set_defaults(func=fileshare_unexport)

def fileshare_unexport(args):
    try:
        
        if(args.protocol == "CIFS"):
            if(args.share == None):
                raise SOSError(SOSError.CMD_LINE_ERR,
                               'error: -share is required for CIFS unexport')
        else:
            if(args.security == None):
                raise SOSError(SOSError.CMD_LINE_ERR,
                               'error: -security is required for ' + args.protocol + ' unexport')
            if(args.permission == None):
                raise SOSError(SOSError.CMD_LINE_ERR,
                               'error: -permission is required for ' + args.protocol + ' unexport')
            if(args.root_user == None):
                raise SOSError(SOSError.CMD_LINE_ERR,
                               'error: -rootuser is required for ' + args.protocol + ' unexport')

        obj = Fileshare(args.ip, args.port)
        if(not args.tenant):
            args.tenant = ""
        res = obj.unexport(args.tenant + "/" + args.project + "/" + args.name,
                           args.security, args.permission, args.root_user,
                           args.protocol, args.share, args.subdir, args.sync)
#        if(args.sync == False):
#            return common.format_json_object(res)

    except SOSError as e:
        if (e.err_code == SOSError.NOT_FOUND_ERR):
            raise SOSError(e.err_code, "Unexport failed: " + e.err_text)
        else:
            raise e

# fileshare ingest routines

def unmanaged_parser(subcommand_parsers, common_parser):
    unmanaged_parser = subcommand_parsers.add_parser('unmanaged',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Unmanaged volume operations')
    subcommand_parsers = unmanaged_parser.add_subparsers(help='Use one of the commands')

    #ingest unmanaged volume
    ingest_parser = subcommand_parsers.add_parser('ingest',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='ingest unmanaged fileshares into ViPR')
    mandatory_args = ingest_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-vpool', '-vp',
                                metavar='<vpool>',
                                dest='vpool',
                                help='Name of vpool',
                                required=True)
    ingest_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of project',
                                required=True)
    mandatory_args.add_argument('-varray', '-va',
                                metavar='<varray>',
                                dest='varray',
                                help='Name of varray',
                                required=True)
    mandatory_args.add_argument('-filesystems', '-fs',
                                metavar='<filesystems>',
                                dest='filesystems',
                                help='Name or id of filesystem',
                                nargs='+',
                                required=True)

    #show unmanaged volume
    umshow_parser = subcommand_parsers.add_parser('show',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Show unmanaged volume')
    mandatory_args = umshow_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-filesystem', '-fs',
                                metavar='<filesystem>',
                                dest='filesystem',
                                help='Name or id of filesystem',
                                required=True)

    ingest_parser.set_defaults(func=unmanaged_filesystem_ingest)

    umshow_parser.set_defaults(func=unmanaged_filesystem_show)

def unmanaged_filesystem_ingest(args):
    obj = Fileshare(args.ip, args.port)
    try:
        if(not args.tenant):
            args.tenant = ""
        res = obj.unmanaged_filesystem_ingest(args.tenant, args.project,
                             args.varray, args.vpool, args.filesystems)
    except SOSError as e:
        raise e

def unmanaged_filesystem_show(args):
    obj = Fileshare(args.ip, args.port)
    try:
        res = obj.unmanaged_filesystem_show(args.filesystem)
        return common.format_json_object(res)
    except SOSError as e:
        raise e
            
# Fileshare Show routines
 
def show_parser(subcommand_parsers, common_parser):
    show_parser = subcommand_parsers.add_parser('show',
                                description='ViPR Filesystem Show CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Show details of filesystem')
    mandatory_args = show_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-name', '-n',
                                dest='name',
                                metavar='<filesystemname>',
                                help='Name of Filesystem',
                                required=True)
    show_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of project',
                                required=True)
    show_parser.add_argument('-xml',
                            dest='xml',
                            action="store_true",
                            help='Display in XML format')
    show_parser.set_defaults(func=fileshare_show)

def fileshare_show(args):
    obj = Fileshare(args.ip, args.port)
    try:
        if(not args.tenant):
            args.tenant = ""
        res = obj.show(args.tenant + "/" + args.project + "/" + args.name,
                       False, args.xml)
        if(args.xml):
            return common.format_xml(res)
        return common.format_json_object(res)
    except SOSError as e:
        raise e

def show_exports_parser(subcommand_parsers, common_parser):
    show_exports_parser = subcommand_parsers.add_parser('show-exports',
                                description='ViPR Filesystem Show exports CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Show export details of filesystem')
    mandatory_args = show_exports_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-name', '-n',
                                dest='name',
                                metavar='<filesystemname>',
                                help='Name of Filesystem',
                                required=True)
    show_exports_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of project',
                                required=True)
    show_exports_parser.set_defaults(func=fileshare_exports_show)

def fileshare_exports_show(args):
    obj = Fileshare(args.ip, args.port)
    try:
        if(not args.tenant):
            args.tenant = ""
        res = obj.get_exports(args.tenant + "/" + args.project + "/" + args.name)
        if(res):
            return common.format_json_object(res)
    except SOSError as e:
        raise e


# Fileshare List routines

def list_parser(subcommand_parsers, common_parser):
    list_parser = subcommand_parsers.add_parser('list',
                                description='ViPR Filesystem List CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='List filesystems')
    mandatory_args = list_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of Project',
                                required=True)
    list_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    list_parser.add_argument('-verbose', '-v',
                                dest='verbose',
                                help='List filesystems with details',
                                action='store_true')
    list_parser.add_argument('-long', '-l',
                                dest='long',
                                help='List filesystems having more headers',
                                action='store_true')
    list_parser.set_defaults(func=fileshare_list)

def fileshare_list(args):
    obj = Fileshare(args.ip, args.port)
    try:
        if(not args.tenant):
            args.tenant = ""
        result = obj.list_fileshares(args.tenant + "/" + args.project)
        if(len(result) > 0):
            if(args.verbose == False):
                for record in result:
                    if("fs_exports" in record):
                        del record["fs_exports"]
                    if("project" in record and "name" in record["project"]):
                        del record["project"]["name"]
                    if("vpool" in record and "vpool_params" in record["vpool"] 
                       and record["vpool"]["vpool_params"]):
                        for vpool_param in record["vpool"]["vpool_params"]:
                            record[vpool_param["name"]] = vpool_param["value"]
                        record["vpool"] = None
                        
                #show a short table
                from common import TableGenerator
                if(not args.long):
                    TableGenerator(result, ['name', 'capacity_gb',
                                            'protocols']).printTable()
                else:
                    TableGenerator(result, ['name', 'capacity_gb', 'protocols', 'thinly_provisioned']).printTable()
            #show all items in json format
            else:
                return common.format_json_object(result)

        else:
            return
    except SOSError as e:
        raise e


# Fileshare mount routines

def mount_parser(subcommand_parsers, common_parser):
    mount_parser = subcommand_parsers.add_parser('mount',
                                description='ViPR Filesystem Mount CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Mount a filesystem')
    mandatory_args = mount_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-mountdir', '-d',
                                metavar='<mountdir>',
                                dest='mount_dir',
                                help='Path of mount directory',
                                required=True)
    mandatory_args.add_argument('-name', '-n',
                                dest='name',
                                metavar='<filesystemname>',
                                help='Name of Fileshare',
                                required=True)
    mount_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of project',
                                required=True)    

    mount_parser.set_defaults(func=fileshare_mount)

def fileshare_mount(args):
    obj = Fileshare(args.ip, args.port)
    try:
        if(not args.tenant):
            args.tenant = ""
        res = obj.mount(args.tenant + "/" + args.project + "/" + args.name,
                        args.mount_dir)
    except SOSError as e:
            raise e

def task_parser(subcommand_parsers, common_parser):
    task_parser = subcommand_parsers.add_parser('tasks',
                                description='ViPR Filesystem List tasks CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Show details of filesystem tasks')
    mandatory_args = task_parser.add_argument_group('mandatory arguments')
    
    task_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of project',
                                required=True)
    task_parser.add_argument('-name', '-n',
                                dest='name',
                                metavar='<filesystemname>',
                                help='Name of filesystem')
    task_parser.add_argument('-id',
                            dest='id',
                            metavar='<opid>',
                            help='Operation ID')
    task_parser.add_argument('-v', '-verbose',
                            dest='verbose',
                            action="store_true",
                            help='List all tasks')
    task_parser.set_defaults(func=fileshare_list_tasks)
    
def fileshare_list_tasks(args):
    if(args.id and not args.name):
        raise SOSError(SOSError.CMD_LINE_ERR, "error: value for -n/-name must be provided when -id is used")
    obj = Fileshare(args.ip, args.port)
    try:
        if(not args.tenant):
            args.tenant = ""
        if(args.id):
            res = obj.list_tasks(args.tenant + "/" + args.project, args.name, args.id)
            if(res):
                return common.format_json_object(res)
        elif(args.name):
            res = obj.list_tasks(args.tenant + "/" + args.project, args.name)
            if(res and len(res) > 0):
                if(args.verbose):
                    return common.format_json_object(res)
                else:
                    from common import TableGenerator
                    TableGenerator(res, ["op_id", "name", "state"]).printTable()
        else:
            res = obj.list_tasks(args.tenant + "/" + args.project)
            if(res and len(res) > 0):
                if(not args.verbose):
                    from common import TableGenerator
                    TableGenerator(res, ["op_id", "name", "state"]).printTable()
                else:
                    return common.format_json_object(res)
        
    except SOSError as e:
            raise e
        
def expand_parser(subcommand_parsers, common_parser):
    expand_parser = subcommand_parsers.add_parser('expand',
                                description='ViPR Filesystem Show CLI usage.',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Show details of filesystem')
    mandatory_args = expand_parser.add_argument_group('mandatory arguments')
    mandatory_args.add_argument('-name', '-n',
                                dest='name',
                                metavar='<filesystemname>',
                                help='Name of Filesystem',
                                required=True)
    expand_parser.add_argument('-tenant', '-tn',
                                metavar='<tenantname>',
                                dest='tenant',
                                help='Name of tenant')
    mandatory_args.add_argument('-project', '-pr',
                                metavar='<projectname>',
                                dest='project',
                                help='Name of project',
                                required=True)
    mandatory_args.add_argument('-size', '-s',
                                help='New size of filesystem: {number}[unit]. ' + 
                                'A size suffix of K for kilobytes, M for megabytes, G for gigabytes, T for ' + 
                                'terabytes is optional.' + 
                                'Default unit is bytes.',
                                metavar='<filesystemsize[kKmMgGtT]>',
                                dest='size',
                                required=True)
    expand_parser.add_argument('-synchronous', '-sync',
                                dest='sync',
                                help='Execute in synchronous mode',
                                action='store_true')
    expand_parser.set_defaults(func=fileshare_expand)

def fileshare_expand(args):
    size = common.to_bytes(args.size)
    if(not size):
        raise SOSError(SOSError.CMD_LINE_ERR, 'error: Invalid input for -size')
    
    obj = Fileshare(args.ip, args.port)
    try:
        if(not args.tenant):
            args.tenant = ""
        
        res = obj.expand(args.tenant + "/" + args.project + 
                          "/" + args.name, size, args.sync) 
    except SOSError as e:
        raise e
    
#
# Fileshare Main parser routine
#

def fileshare_parser(parent_subparser, common_parser):
    # main project parser

    parser = parent_subparser.add_parser('filesystem',
                                description='ViPR filesystem CLI usage',
                                parents=[common_parser],
                                conflict_handler='resolve',
                                help='Operations on filesystem')
    subcommand_parsers = parser.add_subparsers(help='Use one of subcommands')

    # create command parser
    create_parser(subcommand_parsers, common_parser)
    
    # update command parser
    # update_parser(subcommand_parsers, common_parser)

    # delete command parser
    delete_parser(subcommand_parsers, common_parser)

    # show command parser
    show_parser(subcommand_parsers, common_parser)
    
    # show exports command parser
    show_exports_parser(subcommand_parsers, common_parser)

    # export command parser
    export_parser(subcommand_parsers, common_parser)

    # unexport command parser
    unexport_parser(subcommand_parsers, common_parser)

    # list command parser
    list_parser(subcommand_parsers, common_parser)

    # mount command parser
    mount_parser(subcommand_parsers, common_parser)
    
    #expand fileshare parser
    expand_parser(subcommand_parsers, common_parser)
    
    # task list command parser    
    task_parser(subcommand_parsers, common_parser)
    
    # unmanaged filesystem  command parser
    unmanaged_parser(subcommand_parsers, common_parser)

