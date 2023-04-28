# -*- encoding: utf-8 -*-

#import win32com.client
def open_conn(file_name):
    import pythoncom
    pythoncom.CoInitialize()
    conn = win32com.client.Dispatch(r'ADODB.Connection')   
    DSN = 'PROVIDER=Microsoft.Jet.OLEDB.4.0;DATA SOURCE=%s;'%file_name   
    conn.Open(DSN)
    return conn 
def close_conn(conn):
    conn.Close()

def exec_query(conn, sql, key_fld_name = None):
    #rs = win32com.client.Dispatch(r'ADODB.Recordset')
    rs = True
    rs.Open(sql, conn, 1, 3)
    #data = rs.GetRows()
    #rs.RecordCount
    rs_data = {}
    fld_size = {}
    if rs.RecordCount <= 0:
        return rs_data, fld_size
    rs.MoveFirst()
    if not rs.EOF:
        for x in range(rs.Fields.Count):
            fld = rs.Fields.Item(x)
            if fld.Type == 202:
                #only the char type have the size limit
                fld_size[fld.Name] = fld.DefinedSize
            else:
                fld_size[fld.Name] = -1
    idx = 1
    while not rs.EOF:
        flds_dict = {}
        for x in range(rs.Fields.Count):
            flds_dict[rs.Fields.Item(x).Name] = rs.Fields.Item(x).value
        if key_fld_name:
            rs_data[flds_dict.get(key_fld_name)] = flds_dict
        else:
            rs_data[idx] = flds_dict
        idx = idx + 1
        rs.MoveNext()
    return rs_data, fld_size
    
def exec_ddl(conn, sql_statement):
    print sql_statement
    conn.Execute(sql_statement)    
   

