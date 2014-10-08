#!/usr/bin/env python
#/*******************************************************************************
# Copyright (c) 2012 IBM Corp.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#/*******************************************************************************
from time import sleep
from sys import path

import os
import prettytable
#import fnmatch

_home = os.environ["HOME"]
#for _path, _dirs, _files in os.walk(os.path.abspath(_home)):
#    for _filename in fnmatch.filter(_files, "code_instrumentation.py") :
#        path.append(_path.replace("/lib/auxiliary",''))
#        break
path[0] = path[0].replace("clients",'') 

from lib.api.api_service_client import *

def main() :
    '''
    TBD
    '''
    _timeout = 240
    _check_interval = 30
    _runtime_samples = 3
    _api_endpoint = "10.106.63.204"
    #_api_endpoint = "10.51.87.111"
    _api_port = "7070"
    _cloud_name = "HCC"
    
    _api = APIClient("http://" + _api_endpoint + ':' + _api_port)

    _test_results_table = prettytable.PrettyTable(["Virtual Application", \
                                                   "Management Report Pass?", \
                                                   "Runtime Report Pass?"])

    for _type in [ "cassandra_ycsb", "coremark", "ddgen", "filebench", "hadoop", "nullworkload" ] :

        _mgt_pass, _rt_pass = deploy_virtual_application(_api, _type, _runtime_samples, _timeout, _check_interval)

        _results_row = []
        _results_row.append(_type)
        _results_row.append(str(_mgt_pass))
        _results_row.append(str(_rt_pass))

        _test_results_table.add_row(_results_row)

    print _test_results_table
    
    return True
    
def deploy_virtual_application(apiconn, application_type, runtime_samples, timeout, check_interval) :
    '''
    TBD
    '''
    try :
        _vapp = None
        _management_metrics_pass = False
        _runtime_metrics_pass = False

        _cloud_name = apiconn.cldlist()[0]["name"]
        _crt_m = apiconn.cldshow(_cloud_name,"mon_defaults")["crt_m"].split(',')
        _dst_m = apiconn.cldshow(_cloud_name,"mon_defaults")["dst_m"].split(',')

        _msg = "Creating a new Virtual Application Instance with type \"" 
        _msg += application_type + "\" on cloud \"" + _cloud_name + "\"..."
        print _msg
        _vapp = apiconn.appattach(_cloud_name, application_type)

        _msg = "    Virtual Application \"" + _vapp["name"] + "\" deployed successfully"    
        print _msg

        _msg = "    Checking reported provisioning metrics..." 
        print _msg
        # Get some data from the monitoring system
        for _vm in _vapp["vms"].split(",") :
            _vm_uuid, _vm_role, _vm_name = _vm.split("|") 
            _management_metrics = apiconn.get_latest_management_data(_cloud_name, _vm_uuid)
            for _metric in _crt_m :
                _msg = "        Checking metric \"" + _metric + "\"..."
                print _msg,
                if _metric not in _management_metrics :
                    print "NOK"
                else :
                    _value = int(_management_metrics[_metric])
                    print str(_value) + " OK"

        _msg = "    Reported provisioning metrics OK" 
        print _msg
        _management_metrics_pass = True

        if _management_metrics_pass :
            _msg = "    Checking for at least " + str(runtime_samples) + " application"
            _msg += " performance metric samples..."
            print _msg
            _initial_time = int(time())
            _curr_time = 0
            _collected_samples = 0

            _app_m = apiconn.typeshow(_cloud_name, application_type)["reported_metrics"].split(',')
            _app_m += [ "app_load_profile", "app_load_id", "app_load_level"]

            _load_manager_vm_uuid = _vapp["load_manager_vm"]
            while _curr_time < timeout and _collected_samples < runtime_samples :
                try :
                    _runtime_metrics = apiconn.get_latest_app_data(_cloud_name, _load_manager_vm_uuid)
                    
                    for _metric in _app_m :
                        
                        if not _metric.count("app_") :
                            _metric = "app_" + _metric

                        _msg = "        Checking metric \"" + _metric + "\"..."
                        print _msg,                
                        if _metric not in _runtime_metrics :
                            print "NOK"
                        else :
                            if not _metric.count("load_profile") :
                                _value = float(_runtime_metrics[_metric]["val"])
                            print str(_value) + " OK"
                            if _metric == "app_load_id" :
                                _collected_samples = _value                    
                except :
                    _curr_time = int(time()) - _initial_time                    
                    _msg = "        No application performance metrics reported after "
                    _msg += str(_curr_time) + " seconds"
                    print _msg

                _curr_time = int(time()) - _initial_time
                sleep(check_interval)

            if _collected_samples >= runtime_samples :
                _runtime_metrics_pass = True
                _msg = "    Reported application performance metrics OK"
                print _msg

        _msg = "    Destroying Virtual Application \"" + _vapp["name"] + "\"..."
        print _msg
    
        apiconn.appdetach(_cloud_name, _vapp["uuid"])

        _msg = "    Checking reported deprovisioning metrics..." 
        print _msg
        # Get some data from the monitoring system
        for _vm in _vapp["vms"].split(",") :
            _vm_uuid, _vm_role, _vm_name = _vm.split("|") 
            _management_metrics = apiconn.get_management_data(_cloud_name, _vm_uuid)
            for _metric in _dst_m :
                _msg = "        Checking metric \"" + _metric + "\"..."
                print _msg,
                if _metric not in _management_metrics :
                    _management_metrics_pass = False
                    print "NOK"
                else :
                    _value = int(_management_metrics[_metric])                        
                    print str(_value) + " OK"

        if _management_metrics_pass :
            _msg = "    Reported deprovisioning metrics OK" 
            print _msg

        _vapp = None

    except APIException, obj :
        error = True
        print "API Problem (" + str(obj.status) + "): " + obj.msg
    
    except APINoSuchMetricException, obj :
        error = True
        print "API Problem (" + str(obj.status) + "): " + obj.msg
    
    except KeyboardInterrupt :
        print "Aborting this APP."
    
    except Exception, msg :
        error = True
        print "Problem during experiment: " + str(msg)
    
    finally :
        if _vapp is not None :
            try :
                if not (_management_metrics_pass and _runtime_metrics_pass) :
                    _msg = "Destroying Virtual Application \"" + _vapp["name"] + "\"..."
                    print _msg             
                    apiconn.appdetach(_cloud_name, _vapp["uuid"])
            except APIException, obj :
                print "Error finishing up: (" + str(obj.status) + "): " + obj.msg

        return _management_metrics_pass, _runtime_metrics_pass
    
main()