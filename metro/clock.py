# -*- coding: utf-8 -*-  
'''
Created on Nov 13, 2014

@author: John.Wang
'''
from win32com.client import Dispatch
from win32com.client import DispatchWithEvents
#from zk.demo.IC_db import IC_DB  
import sys  
from datetime import datetime  
import time
class ClockEvents:
    def OnFinger(self):
        print "OnFinger"
    def OnFingerFeature(self):
        print "OnFinger"
    def OnVerify(self):
        print "Visible changed:"
    def OnConnected(self):
        print "OnConnected"
    def OnDisConnected(self):
        print "OnDisConnected"
        
#from win32com.client import gencache
#mod = gencache.EnsureModule(...) # use 'makepy -i' to see the params
#ob = mod.Application()
#objCybio = win32com.client.DispatchWithEvents(ob, CybioEvents)

        
#ie = DispatchWithEvents("InternetExplorer.Application", IEEvents)
#ie.Visible = 1
         
devid = 1  
statusNames =(  
              'Tatal adminstrator',  
              'Total users',  
              'Total FP',  
              'Total Password',  
              'Total manage record',  
              'Total In and out record',  
              'Nominal FP number',  
              'Nominal user number',  
              'Nominal In and out record number',  
              'Remain FP number',  
              'Remain user number',  
              'Remain In and out record number')  
  
def syncDateTime(zk):  
    print 'Set Termail Datetime by PC…'  
    if zk.SetDeviceTime(devid):  
        print 'Set Termail Datetime ok'  

        
def downloadLog(zk):  
#    if zk.ReadAllGLogData(devid):  
    verify_modes = {0:'Password',1:'Finger',2:'IC Card'}
    inout_modes = {0:'Check-In',1:'Check-Out',2:'Break-Out',3:'Break-In',4:'OT-In',5:'OT-Out'}
    if zk.ReadGeneralLogData(devid):
        print 'User log list:'  
        i = 0
        while True:  
#            s= zk.GetGeneralLogDataStr(devid,None,None,None,None)
            s= zk.SSR_GetGeneralLogData(devid)  
            if s[0]:  
                #(True, u'118', 1, 0, 2014, 7, 15, 12, 1, 51, 0)
                user_id = s[1]
                v_mode = verify_modes[s[2]]
                io_mode = inout_modes[s[3]]
                log_date = datetime.strptime('%s-%s-%s %s:%s:%s'%s[4:10], '%Y-%m-%d %H:%M:%S')
                print 'Reg No:%s  VerifyMode:%s InOutMode:%s DateTime:%s WorkCode:%s' %(user_id, v_mode, io_mode, log_date, s[10])
                i += 1
#                print i  
            else:  
                break  
        print 'User log list end.'  

def restart(zk):  
    if zk.RestartDevice(devid):
        print "The device will restart!"
    else:
        print "The device request restart failed!"

def poweroff(zk):  
    if zk.PowerOffDevice(devid):
        print "The device will restart!"
    else:
        print "The device request restart failed!"
                     
def readDeviceStatus(zk):  
    s = zk.GetFirmwareVersion(devid,None)  
    if s[0]:  
        print 'firmware Version:',s[1]  
    s = zk.GetSerialNumber(devid,None)  
    if s[0]:  
        print 'Serial Number:%s' %(s[1])  
    s = zk.GetProductCode(devid,None)  
    if s[0]:  
        print 'Product Code:%s' %(s[1])  
    s= zk.GetDeviceTime(devid,None,None,None,None,None,None)  
    if s[0]:  
        print 'Device Time:' ,(s[1:8])  
    for i in range(1,12):  
        s= zk.GetDeviceStatus(devid,i,None)  
        if s[0]:  
            print '%s:%s' %(statusNames[i-1],s[1])  
      
  
def connectToZK(zk):  
    devPort = 4370  
    devIPAddr = '10.1.2.53'
      
    flag = zk.Connect_Net(devIPAddr,devPort)  
    print 'Connect flag:%d' %flag  
    if flag:  
        print 'Device Connected.'  
    else:
        print 'Device Connect failed.'
    return flag  

'''
BeginBatchUpdata
BatchUpdata

SSR_SetUserinfo
SSR_SetUserTmpStr

SetStrCardNumber
SSR_SetUserInfo

======
设置卡号
(attribute:cardnumber or
SetStrCardNumber)

登记用户及密码
上传用户信息到机器，若机器原来没用该用户，则
创建用户
(SSR_SetUserInfo)

登记指纹
上传指纹模版给指定用户
(SSR_SetUserTmpStr或SetUserTmpExStr)

CardNumber
================

GetStrCardNumber
'''        
usersInfo=[  
           ['204113386','a1',3],  
           ['-491435564','a2',4],  
           ['1550229372','a3',5]  
           ]  

def TestUserFP(zk):
    for i in range(0,10):
        fp = zk.GetUserTmpExStr(devid,140,i)
        #[True,'FP Str',strLen)
        print fp
  
    print zk.SSR_DelUserTmp(devid,800,0)
    FPData = 'TG1TUzIxAAAFLjEECAUHCc7QAAAdL2kBAAAAhdMtuC4mAI8PoADpABYhmQA5AI0PpAA4LoQPNgBFAMYPYi5MAAoPQQCLAHwhIABaAPcPggBnLnYPQwBsAMUPKS5yAGsPTgC2AHYhVgCSAGwP6QCTLmEPuQCWANoP2C6XABoP0ABcAJ8hoQCpACIPqQCrLnIPwgCyAGQP0C64ACUPIQAKAEghzwDVAC8PrADTLiEPnQDeAP8NxC7lADkPYQAiACchkADqAK0NaADvLkQN9gDsAOoPUy74ACYPZADGARcheQAIAZYPeQANL1UPOwATAeIPWy4XARkP0ADfAU8hlgAeAeAPLQAbL0YPvwAoAZoPKi4vASsOmQD3AYIhQQA1AR0OVQA5L4oPOQA/AW8OaFFjBmOHxYish+K9yHziAmeF6HxvI3eHmYzeDG+NLKr3kuKWpXj4BUNWuI9q9H6BnXs8K7wBUIuYjzCWDEDEdwL0pHd4/Ucmy/g6+cJvJ/Ub2fZgaYaVgw/82a2z9er93IOofjjVRwRqgVOJcwlXeApR7X21C1CH7Kuk+xaM/++WK0YBsPkdDwaRcAGz0CeuqYxh9YsBICO89Y7lMQVw/Zw9tHTVazIaEA00I7yb6wCf6R76cDowBZIMCex4+XxTdIVWfH5xiA9v2tsRrvyWDZsRMCdXhB70me74BtDV3FnqVDpOBP63xc70BRbeDF/aYD+AgSoEWP9wqfcEvXf19R75EQfHguYtsI+BgV+HNsj8pP8dIFTEAusKnAMAaAz9OwcFRxAMwv1oBMWQFyc0BwCtEhOQVwEuwRITYAkA6hMFZcA+EgAsGcPBQdFKwf/Aa2HMAC4PAlTAwE4FxcEvPVUHAKMrDDpV+jsBBi/3Rj6WwEJ7WgcAoTAXtlkRLg0498A7U49H+u5lCABcPIO0wcXqEQA6Qv1Q7sD60GpgBQAyRr/CxO4FADpHBmzLAG5lBzhMwf9xOgUFE099wnYOAK5RCe7BP1Vz/xDFJVzZOf9D/z7BgQYFbWJ6fsIMAIJo+NH/wD1MwRLFAWzTwv9BVP9HgcAPLkZuA//C/QX/PSoBKHFwiAfFS3FZioMEACp3roAILjGT6f7B+gT/+9E5/wkAU5S1kH3vBAAolWTCqwkFk5cawP7BSgUEBc+XFlQGACtfXnfuAgC7miLAwQDbtB9vBwDUnNtW+tMPAGiqfcRXg4GnCwCkqyD/Ov767P8zDwBwrsP8NNH9/v/6/P3kEwXtr6R8wYTBBcPGTMOGCgBosbHCxu3Ag8INAMZzKcXuwcAv/jsHxdm/MP/BwMD9BcXUuAdqCAERwT2T/jktEAcqTP0TxSPO+UAz/f3/MP5AEy7K0a2Lw1oGdcaoY5ILAB3SlsLE7WOQCwAj04l8x+54wQMAbNXW/AMu09grPf4KxczcH0b+/zAEAK/aJdHAAwBo3ysHCgVn50CMkogMxZHjmsLDxMXExQbDxewEAMLnN//9AwVx6zHFBABlLyesKgH67ScrBsUI6mfDwUwFAK0qPfnT/AYA9PAwBf/50QUAn/JJFM8AidfBxMLExccDpQMuVv0rw8KD0hCILt3GwafEqQaTkr/BwgkQuAuV/SUdBxC+DEb87QYVIwxAi8MMEPoWLOzDwf/Cw8JbBxUXFjDDi8AF1V4fMIkGEMwdSTr/+dUFENMeQzHZEJ4O7MXBo8CLAYbG7cCSdcDCwAQEFcojRi4EEOvnQCYqEcAsUx8E1UQzMnkDEAQ5NAEEFW44J50A'
    print zk.SetUserTmpExStr(devid,800,0,1,FPData)
    #(True, 1, u'TG1TUzIxAAAFLjEECAUHCc7QAAAdL2kBAAAAhdMtuC4mAI8PoADpABYhmQA5AI0PpAA4LoQPNgBFAMYPYi5MAAoPQQCLAHwhIABaAPcPggBnLnYPQwBsAMUPKS5yAGsPTgC2AHYhVgCSAGwP6QCTLmEPuQCWANoP2C6XABoP0ABcAJ8hoQCpACIPqQCrLnIPwgCyAGQP0C64ACUPIQAKAEghzwDVAC8PrADTLiEPnQDeAP8NxC7lADkPYQAiACchkADqAK0NaADvLkQN9gDsAOoPUy74ACYPZADGARcheQAIAZYPeQANL1UPOwATAeIPWy4XARkP0ADfAU8hlgAeAeAPLQAbL0YPvwAoAZoPKi4vASsOmQD3AYIhQQA1AR0OVQA5L4oPOQA/AW8OaFFjBmOHxYish+K9yHziAmeF6HxvI3eHmYzeDG+NLKr3kuKWpXj4BUNWuI9q9H6BnXs8K7wBUIuYjzCWDEDEdwL0pHd4/Ucmy/g6+cJvJ/Ub2fZgaYaVgw/82a2z9er93IOofjjVRwRqgVOJcwlXeApR7X21C1CH7Kuk+xaM/++WK0YBsPkdDwaRcAGz0CeuqYxh9YsBICO89Y7lMQVw/Zw9tHTVazIaEA00I7yb6wCf6R76cDowBZIMCex4+XxTdIVWfH5xiA9v2tsRrvyWDZsRMCdXhB70me74BtDV3FnqVDpOBP63xc70BRbeDF/aYD+AgSoEWP9wqfcEvXf19R75EQfHguYtsI+BgV+HNsj8pP8dIFTEAusKnAMAaAz9OwcFRxAMwv1oBMWQFyc0BwCtEhOQVwEuwRITYAkA6hMFZcA+EgAsGcPBQdFKwf/Aa2HMAC4PAlTAwE4FxcEvPVUHAKMrDDpV+jsBBi/3Rj6WwEJ7WgcAoTAXtlkRLg0498A7U49H+u5lCABcPIO0wcXqEQA6Qv1Q7sD60GpgBQAyRr/CxO4FADpHBmzLAG5lBzhMwf9xOgUFE099wnYOAK5RCe7BP1Vz/xDFJVzZOf9D/z7BgQYFbWJ6fsIMAIJo+NH/wD1MwRLFAWzTwv9BVP9HgcAPLkZuA//C/QX/PSoBKHFwiAfFS3FZioMEACp3roAILjGT6f7B+gT/+9E5/wkAU5S1kH3vBAAolWTCqwkFk5cawP7BSgUEBc+XFlQGACtfXnfuAgC7miLAwQDbtB9vBwDUnNtW+tMPAGiqfcRXg4GnCwCkqyD/Ov767P8zDwBwrsP8NNH9/v/6/P3kEwXtr6R8wYTBBcPGTMOGCgBosbHCxu3Ag8INAMZzKcXuwcAv/jsHxdm/MP/BwMD9BcXUuAdqCAERwT2T/jktEAcqTP0TxSPO+UAz/f3/MP5AEy7K0a2Lw1oGdcaoY5ILAB3SlsLE7WOQCwAj04l8x+54wQMAbNXW/AMu09grPf4KxczcH0b+/zAEAK/aJdHAAwBo3ysHCgVn50CMkogMxZHjmsLDxMXExQbDxewEAMLnN//9AwVx6zHFBABlLyesKgH67ScrBsUI6mfDwUwFAK0qPfnT/AYA9PAwBf/50QUAn/JJFM8AidfBxMLExccDpQMuVv0rw8KD0hCILt3GwafEqQaTkr/BwgkQuAuV/SUdBxC+DEb87QYVIwxAi8MMEPoWLOzDwf/Cw8JbBxUXFjDDi8AF1V4fMIkGEMwdSTr/+dUFENMeQzHZEJ4O7MXBo8CLAYbG7cCSdcDCwAQEFcojRi4EEOvnQCYqEcAsUx8E1UQzMnkDEAQ5NAEEFW44J50A', 1768)
    print zk.GetUserTmpExStr(devid,800,0)
                    
def TestUserInfo(zk):  
    '''
    普通/登记员/管理员, 后两者可以进入考勤机的管理界面
    (True, u'800', u'', 0, True)
    (True, u'\u5f20\u80b2\u4f1f Zhang yuwei \x00\uffff\uaddc', u'', 1, True)
    (True, u'\u738b\u9501\u67f1John wang\x00\u74fe\u99d5', u'123', 3, True)    
    '''
#    print zk.SSR_GetUserInfo(devid,800)
#    print zk.SSR_GetUserInfo(devid,3)
#    print zk.SSR_GetUserInfo(devid,140)
    
#    cardNo = '0111111112'
#    zk.SetStrCardNumber(cardNo)        
#    zk.SSR_SetUserInfo(devid,800,u'测试','123',0,True)
    
#    if zk.ReadAllUserID(devid):
#        while True:  
#            s= zk.SSR_GetAllUserInfo(devid)  
#            if s[0]:  
#                #user_id, name, password, privilege, enabled
#                #(True, u'800', u'\u5a34\u5b2d\u762f\x00\uaddc\u74fe', u'123', 0, True)
#                emp_code = '%03d'%(long(s[1]),)
#                print s
#            else:  
#                break  
    
def SendUserInfo(zk):  
    cardNo = '0111111112'
    zk.SetStrCardNumber(cardNo)        
    zk.SSR_SetUserInfo(devid,800,'测试','123',0,True)
    
      
    for user in usersInfo:  
        print user  
        zk.SetStrCardNumber(user[0])  
        s = zk.SetUserInfo(devid,user[2],user[1],None,0,True)  
        if s:  
            print 'send user %s info to device,Card No:%s ' %(user[1],user[0])  
            
#    db = IC_DB()  
#    users = db.getUserInfo()  
    users = [('001',1,'user01'),('002',2,'user02')]
    usersCount = len(users)  
      
    if usersCount>0:  
        print 'Sending some user info to device…', datetime.now()  
        #zk.BeginBatchUpdate(devid,1)  
        for user in users:  
            zk.SetStrCardNumber(user[1])  
            s = zk.SetUserInfo(devid,user[0],user[2],None,0,True)  
            if s and usersCount < 10:  
                print 'send user %s info to device,Card No:%s ' %(user[2],user[0])  
        #if len(users)>0:  
        #if zk.BatchUpdate(devid):  
        print 'Send %d user info to device.' %(len(users)),datetime.now()  
  
def main():  
      
    zk = Dispatch('zkemkeeper.ZKEM')  
#    zk = DispatchWithEvents("zkemkeeper.ZKEM", ClockEvents)
#    DispatchWithEvents.
      
    #sdkVersion = create_string_buffer(”,256)  
    sdkVersion = zk.GetSDKVersion(None)  
    if sdkVersion[0]:  
        print 'sdkVersion:' , sdkVersion[1]  
        if connectToZK(zk):  
#            zk.RegEvent(devid,65535)
#            readDeviceStatus(zk)  
#            syncDateTime(zk)    
#            downloadLog(zk)  
#            for i in range(1,10):
#            zk.Beep(1000)
            TestUserFP(zk)
#            TestUserInfo(zk)
            zk.Disconnect()  
            print 'Disconnect…'  
    print 'Done'  
         
if __name__ == '__main__':  
    main()  
'''
import pymssql  
class IC_DB:  
    def __init__(self):  
    def getUserInfo(self):  
        con = pymssql.connect(host='localhost,1433', user='sa', password='',database ='IC_DB')  
        cur = con.cursor()  
        cur.execute(operation='Select top 5 a.card_id,a.snr,b.user_name ,b.user_code FROM ztx_card_init a ,pub_user b,pub_card c \
        Where a.card_id = c.Card_id1 AND c.User_uid = b.user_uid')  
        return cur.fetchall() 
'''        