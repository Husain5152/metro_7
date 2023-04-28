# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time

from openerp import pooler, tools
from openerp.report import report_sxw
from openerp.report.interface import report_rml
from openerp.tools import to_xml

class mto_design_print(report_rml):
    def create(self, cr, uid, ids, datas, context):
#        data = datas['form']
        design_obj = pooler.get_pool(cr.dbname).get('mto.design')
        data = design_obj.browse(cr, uid, ids[0], context=context)
                
        _divide_columns_for_matrix = 0.7
        _display_ans_in_rows = 5
        #default A4 size
        _pageSize = ('21.1cm','29.7cm')

        _frame_width = tools.ustr(_pageSize[0])
        _frame_height = tools.ustr(float(_pageSize[1].replace('cm','')) - float(1.90))+'cm'
        _tbl_widths = tools.ustr(float(_pageSize[0].replace('cm','')) - float(2.10))+'cm'
        rml ="""<document filename="Production Configuration.pdf">
                <template pageSize="("""+_pageSize[0]+""","""+_pageSize[1]+""")" title='Options' author="MTT" allowSplitting="20" >
                    <pageTemplate id="first">
                        <frame id="first" x1="0.0cm" y1="1.0cm" width='"""+_frame_width+"""' height='"""+_frame_height+"""'/>
                        <pageGraphics>
                            <lineMode width="1.0"/>
                            <lines>1.0cm """+tools.ustr(float(_pageSize[1].replace('cm','')) - float(1.00))+'cm'+""" """+tools.ustr(float(_pageSize[0].replace('cm','')) - float(1.00))+'cm'+""" """+tools.ustr(float(_pageSize[1].replace('cm','')) - float(1.00))+'cm'+"""</lines>
                            <lines>1.0cm """+tools.ustr(float(_pageSize[1].replace('cm','')) - float(1.00))+'cm'+""" 1.0cm 1.00cm</lines>
                            <lines>"""+tools.ustr(float(_pageSize[0].replace('cm','')) - float(1.00))+'cm'+""" """+tools.ustr(float(_pageSize[1].replace('cm','')) - float(1.00))+'cm'+""" """+tools.ustr(float(_pageSize[0].replace('cm','')) - float(1.00))+'cm'+""" 1.00cm</lines>
                            <lines>1.0cm 1.00cm """+tools.ustr(float(_pageSize[0].replace('cm','')) - float(1.00))+'cm'+""" 1.00cm</lines>"""
        #page number
        rml +="""
                <fill color="gray"/>
                <setFont name="Helvetica" size="10"/>
                <drawRightString x='"""+tools.ustr(float(_pageSize[0].replace('cm','')) - float(1.00))+'cm'+"""' y="0.6cm">Page : <pageNumber/> </drawRightString>"""
        rml +="""</pageGraphics>
                    </pageTemplate>
                </template>
                  <stylesheet>
                    <blockTableStyle id="Standard_Outline">
                      <blockAlignment value="LEFT"/>
                      <blockValign value="TOP"/>
                      <blockTopPadding length="0"/>
                      <blockBottomPadding length="0"/>
                      <blockLeftPadding length="0"/>
                      <blockRightPadding length="0"/>
                    </blockTableStyle>
                    <blockTableStyle id="Table1">
                      <blockAlignment value="LEFT"/>
                      <blockValign value="TOP"/>
                      <blockTopPadding length="1"/>
                      <blockBottomPadding length="1"/>
                      <blockLeftPadding length="1"/>
                      <blockRightPadding length="1"/>
                    </blockTableStyle>
                    <blockTableStyle id="Tableau1">
                      <blockAlignment value="LEFT"/>
                      <blockValign value="TOP"/>
                      <blockTopPadding length="1"/>
                      <blockBottomPadding length="1"/>
                      <blockLeftPadding length="1"/>
                      <blockRightPadding length="1"/>
                    </blockTableStyle>
                    <blockTableStyle id="table_attr">
                      <blockAlignment value="LEFT"/>
                      <blockValign value="TOP"/>
                      <lineStyle kind="LINEABOVE" colorName="#e6e6e6" start="0,0" stop="0,0"/>
                      <lineStyle kind="LINEBELOW" colorName="#e6e6e6" start="0,-1" stop="0,-1"/>
                      <lineStyle kind="LINEBELOW" colorName="#e6e6e6" start="0,-1" stop="0,-1"/>
                      <blockTopPadding length="1"/>
                      <blockBottomPadding length="1"/>
                      <blockLeftPadding length="1"/>
                      <blockRightPadding length="1"/>
                    </blockTableStyle>
                    <blockTableStyle id="Table_Outer_Notes">
                      <blockAlignment value="LEFT"/>
                      <blockValign value="TOP"/>
                      <blockTopPadding length="1"/>
                      <blockBottomPadding length="1"/>
                      <blockLeftPadding length="1"/>
                      <blockRightPadding length="1"/>
                    </blockTableStyle>
                    <blockTableStyle id="Table_options">
                      <blockAlignment value="LEFT"/>
                      <blockValign value="TOP"/>
                      <blockTopPadding length="1"/>
                      <blockBottomPadding length="1"/>
                      <blockLeftPadding length="1"/>
                      <blockRightPadding length="1"/>
                    </blockTableStyle>
                    <initialize>
                      <paraStyle name="all" alignment="justify"/>
                    </initialize>
                    <paraStyle name="P1" fontName="Helvetica-Bold" fontSize="20.0" leading="25" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="P2" fontName="Helvetica" fontSize="6.0" leading="8" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="P3" fontName="Helvetica" fontSize="16.0" leading="20" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="P4" fontName="Helvetica-Bold" fontSize="18.0" leading="22" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="P5" fontName="Helvetica" fontSize="14.0" leading="17" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="opt_item" fontName="Helvetica" fontSize="10.0" leading="13" alignment="LEFT" spaceBefore="30" spaceAfter="0.0"/>
                    <paraStyle name="Standard" fontName="Helvetica"/>
                    <paraStyle name="Text body" fontName="Helvetica" spaceBefore="0.0" spaceAfter="6.0"/>
                    <paraStyle name="Heading" fontName="Helvetica" fontSize="14.0" leading="17" spaceBefore="12.0" spaceAfter="6.0"/>
                    <paraStyle name="Heading 9" fontName="Helvetica-Bold" fontSize="75%" leading="NaN" spaceBefore="12.0" spaceAfter="6.0"/>
                    <paraStyle name="List" fontName="Helvetica" spaceBefore="0.0" spaceAfter="6.0"/>
                    <paraStyle name="Footer" fontName="Helvetica"/>
                    <paraStyle name="Table Contents" fontName="Helvetica"/>
                    <paraStyle name="Table Heading" fontName="Helvetica" alignment="CENTER"/>
                    <paraStyle name="Caption" fontName="Helvetica" fontSize="12.0" leading="15" spaceBefore="6.0" spaceAfter="6.0"/>
                    <paraStyle name="Index" fontName="Helvetica"/>
                    <paraStyle name="Horizontal Line" fontName="Helvetica" fontSize="6.0" leading="8" spaceBefore="0.0" spaceAfter="14.0"/>
                    <paraStyle name="terp_header" fontName="Helvetica-Bold" fontSize="12.0" leading="15" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_tblheader_General" fontName="Helvetica-Bold" fontSize="8.0" leading="10" alignment="LEFT" spaceBefore="6.0" spaceAfter="6.0"/>
                    <paraStyle name="terp_tblheader_Details" fontName="Helvetica-Bold" fontSize="10.0" leading="13" alignment="LEFT" spaceBefore="6.0" spaceAfter="6.0"/>
                    <paraStyle name="terp_default_8" fontName="Helvetica" fontSize="8.0" leading="10" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_default_Bold_8" fontName="Helvetica-Bold" fontSize="8.0" leading="10" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_tblheader_General_Centre" fontName="Helvetica-Bold" fontSize="8.0" leading="10" alignment="CENTER" spaceBefore="6.0" spaceAfter="6.0"/>
                    <paraStyle name="terp_tblheader_General_Right" fontName="Helvetica-Bold" fontSize="8.0" leading="10" alignment="RIGHT" spaceBefore="6.0" spaceAfter="6.0"/>
                    <paraStyle name="terp_tblheader_Details_Centre" fontName="Helvetica-Bold" fontSize="10.0" leading="13" alignment="CENTER" spaceBefore="6.0" spaceAfter="6.0"/>
                    <paraStyle name="terp_tblheader_Details_Right" fontName="Helvetica-Bold" fontSize="10.0" leading="13" alignment="RIGHT" spaceBefore="6.0" spaceAfter="6.0"/>
                    <paraStyle name="terp_default_Right_8" fontName="Helvetica" fontSize="8.0" leading="10" alignment="RIGHT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_default_Centre_8" fontName="Helvetica" fontSize="8.0" leading="10" alignment="CENTER" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_header_Right" fontName="Helvetica-Bold" fontSize="15.0" leading="19" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_header_Centre" fontName="Helvetica-Bold" fontSize="12.0" leading="15" alignment="CENTER" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_default_address" fontName="Helvetica" fontSize="10.0" leading="13" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_default_9" fontName="Helvetica" fontSize="10.0" leading="13" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_default_Bold_9" fontName="Helvetica-Bold" fontSize="10.0" leading="13" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_default_Centre_9" fontName="Helvetica" fontSize="9.0" leading="11" alignment="CENTER" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_default_Right_9" fontName="Helvetica" fontSize="10.0" leading="13" alignment="RIGHT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_default_Bold_9_Right" fontName="Helvetica-Bold" fontSize="10.0" leading="13" alignment="RIGHT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_default_8_Italic" fontName="Helvetica-Oblique" fontSize="8.0" leading="10" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <paraStyle name="terp_default_2" fontName="Helvetica" fontSize="2.0" leading="3" alignment="LEFT" spaceBefore="0.0" spaceAfter="0.0"/>
                    <images/>
                  </stylesheet>
                  <story>"""
        #basic data
        rml += """                    
                    <blockTable colWidths="535.0" style="Table1">
                      <tr>
                        <td>
                          <para style="P1">
                            <font face="Helvetica" size="20.0">Production Configuration """  + to_xml(tools.ustr(data.name)) + """</font>
                          </para>
                        </td>
                      </tr>
                    </blockTable>                  
                    <blockTable colWidths="180.0,159.0,195.0" style="Tableau1">
                      <tr>
                        <td>
                          <para style="P5">Model: """  + to_xml(tools.ustr(data.design_tmpl_id.name)) + """</para>
                        </td>
                        <td>
                          <para style="P5">Price: """  + tools.ustr(data.design_tmpl_id.currency_id.symbol) + tools.ustr(data.list_price) + """</para>
                        </td>
                        <td>
                          <para style="P5">Weight: """  + tools.ustr(data.weight) + """KG</para>
                        </td>
                      </tr>
                    </blockTable>
                """
        design_tmpl = data.design_tmpl_id
        opt_obj = pooler.get_pool(cr.dbname).get('attribute.option')
        for attr_group in design_tmpl.attribute_group_ids:
            rml += """
                    <blockTable colWidths="533.0" style="table_attr">
                        <tr>
                          <td>
                            <para style="P4">"""  + to_xml(tools.ustr(attr_group.name)) + """</para>
                          </td>
                        </tr>
                """            
            for attr in attr_group.attribute_ids:
                attr_label = attr.field_description
                attr_type = attr.attribute_type
                attr_val = getattr(data,attr.name)
                #field label
                rml += """
                        <tr>
                          <td>
                            <para style="P5">%s.%s</para>
                          </td>
                        </tr>
                        """%(attr.sequence,to_xml(design_obj._get_attr_pw_name(data,attr)),)
                #field value
                if attr_type in ('char','text','boolean','integer','date','datetime','float'):
                    if attr_val :
                        rml += """
                            <tr>
                              <td>
                                <para style="opt_item">%s</para>
                              </td>
                            </tr>
                            """%(to_xml(attr_val),)
                    
                elif attr_type == 'select':
                    rml += """
                        <tr>
                          <td>
                                <blockTable colWidths="18.0,516.0" style="Table_options">
                            """           
                    for sel_opt in attr.option_ids:                    
                        rml += """
                                  <tr>
                                    <td>
                                    <illustration>
                                        <fill color="white"/>
                                        <circle x="0.3cm" y="-0.2cm" radius="0.18 cm" fill="yes" stroke="yes"  round="0.1cm"/>
                                """
                        if attr_val and attr_val.id == sel_opt.id:
                            rml += """
                                        <fill color="black"/>
                                        <circle x="0.3cm" y="-0.2cm" radius="0.13 cm" fill="yes" stroke="no"  round="0.1cm"/>
                                """
                        rml += """
                                    </illustration>  
                                    </td>  
                                    <td>
                                      <para style="opt_item">%s</para>
                                    </td>
                                  </tr>    
                                """%(to_xml(opt_obj.name_get(cr,uid,sel_opt.id,context)[0][1]),)
                    
                    rml += """
                                </blockTable>  
                          </td>
                        </tr>
                        """ 
                elif attr_type == 'multiselect':
                    attr_val_ids = [val.id for val in attr_val]
                    rml += """
                        <tr>
                          <td>
                                <blockTable colWidths="18.0,516.0" style="Table_options">
                            """
                    for sel_opt in attr.option_ids:                    
                        rml += """
                                  <tr>
                                    <td>
                                    <illustration>
                                        <fill color="white"/>
                                        <rect x="0.1cm" y="-0.45cm" width="0.4 cm" height="0.4cm" fill="yes" stroke="yes"  round="0.1cm"/>
                                """
                        if sel_opt.id in attr_val_ids:
                            rml += """
                                        <fill color="black"/>
                                        <rect x="0.15cm" y="-0.4cm" width="0.3 cm" height="0.3cm" fill="yes" stroke="no"  round="0.1cm"/>
                                """
                        rml += """
                                    </illustration> 
                                    </td>  
                                    <td>        
                                    <para style="opt_item">%s</para>
                                    </td>
                                  </tr>
                                """%(to_xml(opt_obj.name_get(cr,uid,sel_opt.id,context)[0][1]),)
                    rml += """
                                </blockTable>  
                          </td>
                        </tr>    
                        """                            
            rml += """
                    </blockTable>
                """             
        #the description
        rml += """
                <blockTable colWidths="535.0" style="Table_Outer_Notes">
                  <tr>
                    <td>
                      <para style="terp_default_9">Description:</para>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <para style="terp_default_9">%s</para>
                    </td>
                  </tr>
                </blockTable>
                """%(data.description and data.description or '',)
        rml += """</story></document>"""
        report_type = datas.get('report_type', 'pdf')
        create_doc = self.generators[report_type]
        pdf = create_doc(rml, title=self.title)
        return (pdf, report_type)

mto_design_print('report.mto.design.print', 'mto.design','','')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
