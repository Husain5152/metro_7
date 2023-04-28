# -*- encoding: utf-8 -*-
#!/usr/bin/python
#Python操作Access数据库步骤之1、建立数据库连接

import win32com.client   
conn = win32com.client.Dispatch(r'ADODB.Connection')   
DSN = 'PROVIDER=Microsoft.Jet.OLEDB.4.0;DATA SOURCE=C:/Program Files/ZKTeco/ATT2000.MDB;'   
conn.Open(DSN) 

#Python操作Access数据库步骤之4、用SQL来插入或更新数据
#sql_statement = "Insert INTO USERINFO] ([Badgenumber], [SSN], ) VALUES ('data1', 'data2')"
rs = win32com.client.Dispatch(r'ADODB.Recordset')
#sql_statement = "select 1 from userinfo where badgenumber = '002'"
sql_statement = "select badgenumber,name,gender,ssn,minzu,ophone,title,birthday,hiredday,cardno,pager,street from userinfo"
rs.Open(sql_statement, conn, 1, 3)
#data = rs.GetRows()
#rs.RecordCount
rs_data = []
flds_dict = {}
rs.MoveFirst()
while not rs.EOF:
    for x in range(rs.Fields.Count):
        #print '\'%s\':%s:%s,'%(rs.Fields.Item(x).Name,rs.Fields.Item(x).Type,rs.Fields.Item(x).DefinedSize)
        print '\'%s\':%s:%s,'%(rs.Fields.Item(x).Name,rs.Fields.Item(x).Type,rs.Fields.Item(x).DefinedSize)
        flds_dict[rs.Fields.Item(x).Name] = rs.Fields.Item(x).value
    rs_data.append(flds_dict)
    rs.MoveNext()
print 'Done'   


           
'''
rs.MoveFirst()   
count = 0   
while 1:   
    if rs.EOF:   
        break   
    else:   
        countcount = count + 1 
        rs.RecordCount
        rs.MoveNext()   
print rs.RecordCount
conn.Close() 
'''
'''
#Python操作Access数据库步骤之2、打开一个记录集
rs = win32com.client.Dispatch(r'ADODB.Recordset')   
rs_name = 'USERINFO'#表名   
rs.Open('[' + rs_name + ']', conn, 1, 3) 

#Python操作Access数据库步骤之3、对记录集操作
#rs.AddNew()   
#rs.Fields.Item(1).Value = 'data'   
#rs.Update() 
conn.Close() 

#Python操作Access数据库步骤之4、用SQL来插入或更新数据
conn = win32com.client.Dispatch(r'ADODB.Connection')   
DSN = 'PROVIDER=Microsoft.Jet.OLEDB.4.0;DATA SOURCE=z:/ATT2000.MDB;'  
#sql_statement = "Insert INTO USERINFO] ([Badgenumber], [SSN], ) VALUES ('data1', 'data2')"
sql_statement = "insert into userinfo (badgenumber,ssn,name,gender,title) values ('002','002-ssn','002-name','1','002-title')"   
conn.Open(DSN)   
conn.Execute(sql_statement)   
#conn.Close() 

rs = win32com.client.Dispatch(r'ADODB.Recordset')   
rs_name = 'USERINFO'#表名   
rs.Open('[' + rs_name + ']', conn, 1, 3) 

#Python操作Access数据库步骤之5、遍历记录
rs.MoveFirst()   
count = 0   
while 1:   
    if rs.EOF:   
        break   
    else:   
        countcount = count + 1   
        rs.MoveNext() 

#注意：如果一个记录是空的，那么将指针移动到第一个记录将导致一个错误，因为此时recordcount是无效的。
#解决的方法是：打开一个记录集之前，先将Cursorlocation设置为3，然后再打开记录集，此时recordcount将是有效的。例如：

#rs.Cursorlocation = 3 # don't use parenthesis here   
rs.Open('Select * FROM [Table_Name]', conn) # be sure conn is open   
rs.RecordCount # no parenthesis here either 
'''