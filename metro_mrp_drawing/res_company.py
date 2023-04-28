# -*- coding: utf-8 -*-s
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.report.PyPDF2 import PdfFileWriter, PdfFileReader
import tempfile
import StringIO
import os
from reportlab.pdfgen import canvas
import base64

class res_company(osv.osv):
    _name = 'res.company'
    _inherit = 'res.company'
    _columns = {
        'stamp': fields.binary('Company Stamp'),
        'stamp_landscape': fields.binary('Company Stamp Landscape'),
        'stamp_portrait': fields.binary('Company Stamp Portrait')
    }

    def add_watermark_to_attachments(self, cr, uid, attachment_ids, stamp_pos_x, stamp_pos_y, stamp_size=110,
                                     date_x=False, date_y=False, sign_date=False,
                                     user_sign_x=False, user_sign_y=False,
                                     user_sign_width=False, user_sign_height=False, user_sign= False,
                                     context=None):
        attachment_obj = self.pool.get('ir.attachment')
        user = self.pool.get('res.users').browse(cr, uid, uid)
        user_signature_file_name = False
        watermark_file_name = False
        delete_files = []
        if user.company_id.stamp and len(attachment_ids) > 0:
            watermark_file = tempfile.NamedTemporaryFile(delete=False)
            watermark_file_name = watermark_file.name
            watermark_file.close()
            outputStr = file(watermark_file_name, "wb")
            outputStr.write(user.company_id.stamp.decode('base64'))
            outputStr.close()
            delete_files.append(watermark_file_name)
        if user_sign:
            if user.signature_image:
                user_signature_file = tempfile.NamedTemporaryFile(delete=False)
                user_signature_file_name = user_signature_file.name
                user_signature_file.close()
                outputStr = file(user_signature_file_name, "wb")
                outputStr.write(user.signature_image.decode('base64'))
                outputStr.close()
                delete_files.append(user_signature_file_name)
        old_width = 0
        old_height = 0
        imgTemp = False
        if watermark_file_name:
            for attach_id in attachment_ids:
                attachment = attachment_obj.browse(cr, uid, attach_id, context=context)
                output = PdfFileWriter()
                attach_file = attachment_obj.file_get(cr, uid, attach_id, context=context)
                input = PdfFileReader(attach_file)
                page_cnt = 0
                for page in input.pages:
                    pageBox = page.mediaBox
                    width = pageBox.getLowerRight_x()
                    height = pageBox.getUpperRight_y()
                    if width != old_width or height != old_height:
                        old_height = height
                        old_width = width
                        if imgTemp:
                            imgTemp.close()
                        imgTemp = StringIO.StringIO()
                        imgDoc = canvas.Canvas(imgTemp)
                        imgDoc.setPageSize((width,
                                            height))
                        # Draw image on Canvas and save PDF in buffer
                        imgDoc.drawImage(watermark_file_name,
                                         stamp_pos_x,
                                         stamp_pos_y,
                                         stamp_size, stamp_size, mask='auto')
                        if user_signature_file_name:
                            imgDoc.drawImage(user_signature_file_name,
                                             user_sign_x,
                                             user_sign_y,
                                             user_sign_width, user_sign_height, mask='auto')
                        if sign_date:
                            imgDoc.drawString(date_x, date_y, sign_date)
                        imgDoc.save()

                    if imgTemp:
                        # Use PyPDF to merge the image-PDF into the template
                        watermark_pdf = PdfFileReader(StringIO.StringIO(imgTemp.getvalue()))
                        watermark_page = watermark_pdf.getPage(0)
                        try:
                            page.mergePage(watermark_page)
                        except:
                            raise osv.except_osv(_("Error!"), _('Can not add watermark to page %s of part %s!') % (
                            page_cnt + 1, attachment.name))
                    output.addPage(page)
                    page_cnt += 1

                if page_cnt > 0:
                    temp_drawing_pdf_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_drawing_pdf_file_name = temp_drawing_pdf_file.name
                    temp_drawing_pdf_file.close()
                    outputStream = file(temp_drawing_pdf_file_name, "wb")
                    output.write(outputStream)
                    outputStream.close()
                    delete_files.append(temp_drawing_pdf_file_name)
                    inputStr = file(temp_drawing_pdf_file_name, 'rb')
                    watermark_data = inputStr.read()
                    attachment_obj.write(cr, uid, [attach_id], {'datas': base64.encodestring(watermark_data)})
                    inputStr.close()

            if imgTemp:
                imgTemp.close()
        #Delete all temporary files
        for delete_file in delete_files:
            if os.path.isfile(delete_file):
                os.remove(delete_file)

        return True

res_company()