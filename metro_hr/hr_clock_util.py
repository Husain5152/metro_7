# -*- coding: utf-8 -*-

from win32com.client import Dispatch
from datetime import datetime  
import sys
    
from openerp.tools.translate import _

from openerp.osv import fields, osv
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
    
def clock_connect(clock, ip, port):
    if not clock.Connect_Net(ip,port):
        raise osv.except_osv(_('Error!'), _('Connect to %s:%s failed!')%(ip,port))  

def clock_disconnect(clock):
    #finished beep and disconnect
#    clock.Beep(1000)
    return clock.Disconnect()  

def clock_obj():
    import pythoncom
    pythoncom.CoInitialize()
    clock = Dispatch('zkemkeeper.ZKEM')
    return clock

_statusNames =(  
              'Tatal adminstrator',  
              'Total users',  
              'Total Finger Print',  
              'Total Password',  
              'Total manage record',  
              'Total In and out record',  
              'Nominal Finger Print number',  
              'Nominal user number',  
              'Nominal In and out record number',  
              'Remain Finger Print number',  
              'Remain user number',  
              'Remain In and out record number')
            
def clock_status(zk):  
    devid = 1
    resu = ""
    s = zk.GetFirmwareVersion(devid,None)  
    if s[0]:  resu += 'Firmware Version:%s'%(s[1]) + '\n'
    s = zk.GetSerialNumber(devid,None)  
    if s[0]:  resu += 'Serial Number:%s' %(s[1])  + '\n' 
    s = zk.GetProductCode(devid,None)  
    if s[0]:  resu += 'Product Code:%s' %(s[1])  + '\n' 
    s= zk.GetDeviceTime(devid,None,None,None,None,None,None)  
    if s[0]:
        device_date = datetime.strptime('%s-%s-%s %s:%s:%s'%s[1:7], '%Y-%m-%d %H:%M:%S')  
        resu += 'Device Time:%s' %(device_date)  + '\n' 
    for i in range(1,13):  
        s= zk.GetDeviceStatus(devid,i,None)  
        if s[0]:  resu +=  '%s:%s' %(_statusNames[i-1],s[1])  + "\n"
    return resu

def clock_time_set(zk,clock_time=None):
    devid = 1
    if clock_time:
        zk.SetDeviceTime2(devid, clock_time.year, clock_time.month, clock_time.day, 
                                    clock_time.hour, clock_time.minute, clock_time.second)
        
def clock_user_set(zk, emp, sync_pwd=False, new_clock_pwd = False, sync_fp = False, new_user_fps = None): 
    devid = 1 
    #set base info
    if isinstance(emp.emp_code, type(u' ')):
        clock_emp_code = long(emp.emp_code)  
    clock_emp_role = 0
    if isinstance(emp.clock_role, type(u' ')):
        clock_emp_role = long(emp.clock_role)
    clock_emp_pwd = new_clock_pwd
    if not sync_pwd:
        #if do not sunc password, then use the original pwd to set
        emp_old = clock_user_get(zk, clock_emp_code, pwd=True)
        if emp_old:
            clock_emp_pwd = emp_old['clock_pwd']
    zk.SetStrCardNumber(emp.emp_card_id)           
    zk.SSR_SetUserInfo(devid, clock_emp_code, emp.emp_name, clock_emp_pwd, clock_emp_role, True)
    
    #sync Finger Print
    if sync_fp and new_user_fps:
        for i in range(0,10):
            if new_user_fps[i]:
                zk.SetUserTmpExStr(devid,clock_emp_code,i,1,new_user_fps[i])
            else:
                zk.SSR_DelUserTmp(devid,clock_emp_code,i)

    return True
        
def clock_user_delete(zk, emp_code): 
    devid = 1 
    clock_emp_code = emp_code
    if isinstance(emp_code, type(u' ')):
        clock_emp_code = long(emp_code)
    s = zk.SSR_DeleteEnrollDataExt(devid,clock_emp_code,12)
    return True

def clock_user_get(zk, emp_code, pwd = False, finger_print = False): 
    devid = 1 
    clock_emp_code = emp_code
    if isinstance(emp_code, type(u' ')):
        clock_emp_code = long(emp_code)
    s = zk.SSR_GetUserInfo(devid,clock_emp_code)
    if s[0]:
        #user_name, password, privilege(role), enabled
        #(True, u'\u738b\u9501\u67f1John wang\x00\u74fe\u99d5', u'123', 3, True)
        emp_name = s[1]
        #remove the special character for the Chinese character, starts with '\x00', see above sample data
        emp_name = emp_name[:emp_name.find(u'\x00')]
        emp_card_id = None
        ec = zk.GetStrCardNumber()
        if ec: emp_card_id = ec[1]
        clock_role = str(s[3])
        emp_dict = {'emp_code':emp_code, 'emp_name':emp_name, 'emp_card_id':emp_card_id, 'clock_role':clock_role}
        if pwd:
            emp_dict['clock_pwd'] = s[2]
        if finger_print:
            for i in range(0,10):
                fp = zk.GetUserTmpExStr(devid,clock_emp_code,i)
                #(True, 1, u'TG1TUzIxAAAFLjEECAUHCc7QAAAdL2kBAAAAhdMtuC4mAI8PoADpABYhmQA5AI0PpAA4LoQPNgBFAMYPYi5MAAoPQQCLAHwhIABaAPcPggBnLnYPQwBsAMUPKS5yAGsPTgC2AHYhVgCSAGwP6QCTLmEPuQCWANoP2C6XABoP0ABcAJ8hoQCpACIPqQCrLnIPwgCyAGQP0C64ACUPIQAKAEghzwDVAC8PrADTLiEPnQDeAP8NxC7lADkPYQAiACchkADqAK0NaADvLkQN9gDsAOoPUy74ACYPZADGARcheQAIAZYPeQANL1UPOwATAeIPWy4XARkP0ADfAU8hlgAeAeAPLQAbL0YPvwAoAZoPKi4vASsOmQD3AYIhQQA1AR0OVQA5L4oPOQA/AW8OaFFjBmOHxYish+K9yHziAmeF6HxvI3eHmYzeDG+NLKr3kuKWpXj4BUNWuI9q9H6BnXs8K7wBUIuYjzCWDEDEdwL0pHd4/Ucmy/g6+cJvJ/Ub2fZgaYaVgw/82a2z9er93IOofjjVRwRqgVOJcwlXeApR7X21C1CH7Kuk+xaM/++WK0YBsPkdDwaRcAGz0CeuqYxh9YsBICO89Y7lMQVw/Zw9tHTVazIaEA00I7yb6wCf6R76cDowBZIMCex4+XxTdIVWfH5xiA9v2tsRrvyWDZsRMCdXhB70me74BtDV3FnqVDpOBP63xc70BRbeDF/aYD+AgSoEWP9wqfcEvXf19R75EQfHguYtsI+BgV+HNsj8pP8dIFTEAusKnAMAaAz9OwcFRxAMwv1oBMWQFyc0BwCtEhOQVwEuwRITYAkA6hMFZcA+EgAsGcPBQdFKwf/Aa2HMAC4PAlTAwE4FxcEvPVUHAKMrDDpV+jsBBi/3Rj6WwEJ7WgcAoTAXtlkRLg0498A7U49H+u5lCABcPIO0wcXqEQA6Qv1Q7sD60GpgBQAyRr/CxO4FADpHBmzLAG5lBzhMwf9xOgUFE099wnYOAK5RCe7BP1Vz/xDFJVzZOf9D/z7BgQYFbWJ6fsIMAIJo+NH/wD1MwRLFAWzTwv9BVP9HgcAPLkZuA//C/QX/PSoBKHFwiAfFS3FZioMEACp3roAILjGT6f7B+gT/+9E5/wkAU5S1kH3vBAAolWTCqwkFk5cawP7BSgUEBc+XFlQGACtfXnfuAgC7miLAwQDbtB9vBwDUnNtW+tMPAGiqfcRXg4GnCwCkqyD/Ov767P8zDwBwrsP8NNH9/v/6/P3kEwXtr6R8wYTBBcPGTMOGCgBosbHCxu3Ag8INAMZzKcXuwcAv/jsHxdm/MP/BwMD9BcXUuAdqCAERwT2T/jktEAcqTP0TxSPO+UAz/f3/MP5AEy7K0a2Lw1oGdcaoY5ILAB3SlsLE7WOQCwAj04l8x+54wQMAbNXW/AMu09grPf4KxczcH0b+/zAEAK/aJdHAAwBo3ysHCgVn50CMkogMxZHjmsLDxMXExQbDxewEAMLnN//9AwVx6zHFBABlLyesKgH67ScrBsUI6mfDwUwFAK0qPfnT/AYA9PAwBf/50QUAn/JJFM8AidfBxMLExccDpQMuVv0rw8KD0hCILt3GwafEqQaTkr/BwgkQuAuV/SUdBxC+DEb87QYVIwxAi8MMEPoWLOzDwf/Cw8JbBxUXFjDDi8AF1V4fMIkGEMwdSTr/+dUFENMeQzHZEJ4O7MXBo8CLAYbG7cCSdcDCwAQEFcojRi4EEOvnQCYqEcAsUx8E1UQzMnkDEAQ5NAEEFW44J50A', 1768)
                if fp[0]:
                    emp_dict['clock_fp%s'%(i+1,)] = fp[2]
        return emp_dict
    return False

def clock_user_get_all(zk, ret_dict = False, pwd = False, finger_print = False): 
    devid = 1 
    emps = []
    if ret_dict:
        emps = {}
    if zk.ReadAllUserID(devid):
        while True:  
            s= zk.SSR_GetAllUserInfo(devid)  
            if s[0]:  
                #user_id,user_name, password, privilege(role), enabled
                #(True, u'800', u'\u5a34\u5b2d\u762f\x00\uaddc\u74fe', u'123', 0, True)
                emp_code = '%03d'%(long(s[1]),)
                emp_name = s[2]
                #remove the special character for the Chinese character, starts with '\x00', see above sample data
                emp_name = emp_name[:emp_name.find(u'\x00')]
                emp_card_id = None
                ec = zk.GetStrCardNumber()
                if ec: emp_card_id = ec[1]
                clock_role = str(s[4])
                emp_dict = {'emp_code':emp_code, 'emp_name':emp_name, 'emp_card_id':emp_card_id, 'clock_role':clock_role}
                if pwd:
                    emp_dict['clock_pwd'] = s[3]
                if finger_print:
                    for i in range(0,10):
                        fp = zk.GetUserTmpExStr(devid,long(s[1]),i)
                        #(True, 1, u'TG1TUzIxAAAFLjEECAUHCc7QAAAdL2kBAAAAhdMtuC4mAI8PoADpABYhmQA5AI0PpAA4LoQPNgBFAMYPYi5MAAoPQQCLAHwhIABaAPcPggBnLnYPQwBsAMUPKS5yAGsPTgC2AHYhVgCSAGwP6QCTLmEPuQCWANoP2C6XABoP0ABcAJ8hoQCpACIPqQCrLnIPwgCyAGQP0C64ACUPIQAKAEghzwDVAC8PrADTLiEPnQDeAP8NxC7lADkPYQAiACchkADqAK0NaADvLkQN9gDsAOoPUy74ACYPZADGARcheQAIAZYPeQANL1UPOwATAeIPWy4XARkP0ADfAU8hlgAeAeAPLQAbL0YPvwAoAZoPKi4vASsOmQD3AYIhQQA1AR0OVQA5L4oPOQA/AW8OaFFjBmOHxYish+K9yHziAmeF6HxvI3eHmYzeDG+NLKr3kuKWpXj4BUNWuI9q9H6BnXs8K7wBUIuYjzCWDEDEdwL0pHd4/Ucmy/g6+cJvJ/Ub2fZgaYaVgw/82a2z9er93IOofjjVRwRqgVOJcwlXeApR7X21C1CH7Kuk+xaM/++WK0YBsPkdDwaRcAGz0CeuqYxh9YsBICO89Y7lMQVw/Zw9tHTVazIaEA00I7yb6wCf6R76cDowBZIMCex4+XxTdIVWfH5xiA9v2tsRrvyWDZsRMCdXhB70me74BtDV3FnqVDpOBP63xc70BRbeDF/aYD+AgSoEWP9wqfcEvXf19R75EQfHguYtsI+BgV+HNsj8pP8dIFTEAusKnAMAaAz9OwcFRxAMwv1oBMWQFyc0BwCtEhOQVwEuwRITYAkA6hMFZcA+EgAsGcPBQdFKwf/Aa2HMAC4PAlTAwE4FxcEvPVUHAKMrDDpV+jsBBi/3Rj6WwEJ7WgcAoTAXtlkRLg0498A7U49H+u5lCABcPIO0wcXqEQA6Qv1Q7sD60GpgBQAyRr/CxO4FADpHBmzLAG5lBzhMwf9xOgUFE099wnYOAK5RCe7BP1Vz/xDFJVzZOf9D/z7BgQYFbWJ6fsIMAIJo+NH/wD1MwRLFAWzTwv9BVP9HgcAPLkZuA//C/QX/PSoBKHFwiAfFS3FZioMEACp3roAILjGT6f7B+gT/+9E5/wkAU5S1kH3vBAAolWTCqwkFk5cawP7BSgUEBc+XFlQGACtfXnfuAgC7miLAwQDbtB9vBwDUnNtW+tMPAGiqfcRXg4GnCwCkqyD/Ov767P8zDwBwrsP8NNH9/v/6/P3kEwXtr6R8wYTBBcPGTMOGCgBosbHCxu3Ag8INAMZzKcXuwcAv/jsHxdm/MP/BwMD9BcXUuAdqCAERwT2T/jktEAcqTP0TxSPO+UAz/f3/MP5AEy7K0a2Lw1oGdcaoY5ILAB3SlsLE7WOQCwAj04l8x+54wQMAbNXW/AMu09grPf4KxczcH0b+/zAEAK/aJdHAAwBo3ysHCgVn50CMkogMxZHjmsLDxMXExQbDxewEAMLnN//9AwVx6zHFBABlLyesKgH67ScrBsUI6mfDwUwFAK0qPfnT/AYA9PAwBf/50QUAn/JJFM8AidfBxMLExccDpQMuVv0rw8KD0hCILt3GwafEqQaTkr/BwgkQuAuV/SUdBxC+DEb87QYVIwxAi8MMEPoWLOzDwf/Cw8JbBxUXFjDDi8AF1V4fMIkGEMwdSTr/+dUFENMeQzHZEJ4O7MXBo8CLAYbG7cCSdcDCwAQEFcojRi4EEOvnQCYqEcAsUx8E1UQzMnkDEAQ5NAEEFW44J50A', 1768)
                        if fp[0]:
                            emp_dict['clock_fp%s'%(i+1,)] = fp[2]
                if ret_dict:
                    emps[emp_code] = emp_dict
                else:
                    emps.append(emp_dict)
            else:  
                break      
    return emps

        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
