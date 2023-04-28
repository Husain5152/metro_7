from datetime import datetime
from osv import osv, fields
from operator import mod

def _get_vehicle_year():
    present_year=datetime.now().year
    years=[]
    for i in range(1970,present_year+2):
        this=(str(i),str(i))
        years.append(this)
    return years


class models(osv.osv):
    _name = "mttl.models"
    _description = "Models"
    _columns = {
        'name': fields.char('Model', size=50, required=True),
        'code':fields.char('Code', size=2, required=True)
    }
    def _check_model_code(self, cr, uid, ids, context=None):
        for model in self.browse(cr, uid, ids, context=context):
            if model.code:
                model_ids = self.search(cr, uid, [
                    ('code', '=', model.code),
                    ])
                if len(model_ids) > 1:
                    return False
        return True

    _constraints = [
        (_check_model_code,
            'Model code must be unique.',
            ['code']),
    ]

class years(osv.osv):
    _name = "mttl.years"
    _description = "Years"
    _columns = {
        'name': fields.char('Year', size=4, required=True),
        'code':fields.char('Code', size=1, required=True)
    }
    #++HoangTK - 11/05/2015: Sorting year by descending
    _order = 'name desc'
    #--HoangTK


class location(osv.osv):
    _name = "mttl.locations"
    _description = "Location"
    _columns = {
        'name': fields.char('Location', size=50, required=True),
        'code':fields.char('Code', size=1, required=True)
    }


class country(osv.osv):
    _name = "mttl.countries"
    _description = "Country"
    _rec_name="country_id"
    _columns = {
        'country_id': fields.char('Country', size=50, required=True),
        'code':fields.char('Code', size=1, required=True)
    }


class chassis(osv.osv):
    _name = "mttl.chassis"
    _description = "Chassis"
    _columns = {
        'name': fields.char('Chassiss', size=50, required=True),
        'code':fields.char('Code', size=1, required=True)
    }

class VehicleModel(osv.osv):
    _name = "mttl.vehicle.model"
    _description = "Vehicle Model"
    _columns = {
            'name':fields.char('Model', size=50,required=True),
            'make':fields.many2one('mttl.vehicle.make','Make',required=True)
    }

class VehicleMake(osv.osv):
    _name = "mttl.vehicle.make"
    _description = "Vehicle Make"
    _columns = {
        'name':fields.char('Make', size=20,required=True)
    }

class WarrantyHistory(osv.osv):
    _name = "mttl.warranty.history"
    _description = "Warranty History"
    _columns = {
        'serial_id':fields.many2one('mttl.serials', 'Serial', ondelete='cascade', select=True),
        'date':fields.date('Date'),
        'incident':fields.text('Incident'),
        'action_taken':fields.text('Action Taken'),
        'status':fields.selection([
                   ('in_progress','In Progress'),
                   ('complete','Complete'),
                   ('on_hold','On Hold')], 'Status'),
    }

class partner(osv.osv):
    _inherit="res.partner"
    _columns = {
        'dealer':fields.boolean('Dealer'),
    }
    
class ir_attachment(osv.osv):
    _inherit = "ir.attachment"
    _columns = {
        'mttl_serials_id': fields.many2one('mttl.serials', 'Serial'),
    }
    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if vals.get('mttl_serials_id'):
            vals['mttl_serials_id'] = vals['mttl_serials_id']
            vals['res_model'] = 'mttl.serials'             
            
        return super(ir_attachment, self).create(cr, uid, vals, context)
            
class mttl_serials(osv.osv):
    
    def _generate_serial_number(self, cursor, user, *args):
        try:
            cursor.execute("select serial_number from mttl_serials where id=(select max(id) from mttl_serials)")
            for item in cursor.dictfetchall():
                serial_number = int(item["serial_number"]) + 1
            return serial_number
        except Exception, ex:
            return False

    _inherit = ['mail.thread']
    _name = "mttl.serials"
    _description = "Serials"
    _rec_name="serial"
    _order = "id desc"
    _columns = {
        'serial':fields.char('Serial', size=50, help="Add text here"),
        
        # Information
        'model':fields.many2one('mttl.models', 'Model', required=True, help="Metro Tow Trucks Model"),
        'year':fields.many2one('mttl.years', 'Year', required=True, help="Year of model"),
        'location':fields.many2one('mttl.locations', 'Location', required=True, help="Manufacture location"),
        'country':fields.many2one('mttl.countries', 'Country', required=True, help="Country of manufacture"),
        'chassis':fields.many2one('mttl.chassis', 'Chassis', required=True, help="Who supplied the chassis, or was it sold as a kit?"),
        'partner_id':fields.many2one('res.partner', 'Customer', change_default=True, help="Last known owner of this unit", domain="[('customer','=',True)]"),
        'dealer_id':fields.many2one('res.partner', 'Dealer', change_default=True, help="Last known owner of this unit", domain="[('dealer','=',True)]"),
        'destination_id':fields.many2one('res.partner', 'Destination', change_default=True, help="Last known location of this unit", domain="[('customer','=',True)]"),
        'serial_number':fields.char('Serial Number',size=17, required=True, help="The Computed Serial Number.  Verify that no periods or question marks are present"),
        
        #Vehicle Information
        'chassis_weight': fields.char("Chassis Weight", size=10, help="Weight of Chassis without Wrecker"),
        'wrecker_weight': fields.char("Wrecker Weight", size=10, help="Weight of Wrecker without Chassis"),
        'installed_weight':fields.char("Installed Weight", size=10, help="Completed Vehicle Weight including accessories and fluids"),
        'vehicle_model':fields.many2one("mttl.vehicle.model",'Model', help="Chassis Model"),
        'vehicle_make':fields.many2one('mttl.vehicle.make','Make', help="Chassis Make"),
        'vehicle_year':fields.selection(_get_vehicle_year(),'Year', help="Chassis Year"),
        'vehicle_vin':fields.char('Vehicle VIN', size=20),
        'engine_serial':fields.char('Engine Serial',size=20),

        'chassis_1st_fa':fields.char("Chassis 1st FA", size=10, help="1st Front Axle Weight (without wrecker)"),
        'chassis_2nd_fa':fields.char("Chassis 2nd FA", size=10, help="2nd Front Axle Weight (without wrecker)"),
        'chassis_1st_ra':fields.char("Chassis 1st RA", size=10, help="1st Rear Axle Weight (without wrecker)"),
        'chassis_2nd_ra':fields.char("Chassis 2nd RA", size=10, help="2nd Rear Axle Weight (without wrecker)"),
        'chassis_3rd_ra':fields.char("Chassis 3rd RA", size=10, help="3rd Rear Axle Weight (without wrecker)"),
        'installed_1st_fa':fields.char("Installed 1st FA", size=10, help="1st Front Axle Weight (with wrecker)"),
        'installed_2nd_fa':fields.char("Installed 2nd FA", size=10, help="2nd Front Axle Weight (with wrecker)"),
        'installed_1st_ra':fields.char("Installed 1st RA", size=10, help="1st Rear Axle Weight (with wrecker)"),
        'installed_2nd_ra':fields.char("Installed 2nd RA", size=10, help="2nd Rear Axle Weight (with wrecker)"),
        'installed_3rd_ra':fields.char("Installed 3rd RA", size=10, help="3rd Rear Axle Weight (with wrecker)"),
        'installed_height':fields.char("Installed Height", size=10, help="Highest Point on the Installed Wrecker"),
        'installed_length':fields.char("Installed Length", size=10, help="Overall Length of the Installed Wrecker"),
        'installed_width':fields.char("Installed Width", size=10, help="Overall Width of the Installed Wrecker"),
        'chassis_1st_fa_rating':fields.integer("Chassis 1st FA Rating", size=10, help="1st Front Axle Rating"),
        'chassis_2nd_fa_rating':fields.integer("Chassis 2nd FA Rating", size=10, help="2nd Front Axle Rating"),
        'chassis_1st_ra_rating':fields.integer("Chassis 1st RA Rating", size=10, help="1st Rear Axle Rating"),
        'chassis_2nd_ra_rating':fields.integer("Chassis 2nd RA Rating", size=10, help="2nd Rear Axle Rating"),
        'chassis_3rd_ra_rating':fields.integer("Chassis 3rd RA Rating", size=10, help="3rd Rear Axle Rating"),
        
        #Warranty
        'warranty_start_date':fields.date('Start Date', help="The date the warranty commences"),
        'warranty_finish_date':fields.date('Finish Date', help="The date the warranty expires"),
        'warranty_completion_date':fields.date('Completion Date'),
        'warranty_duration':fields.selection([
                  ('no_warranty', 'No Warranty'),
                  ('30_days','30 Days'),
                  ('60_days','60 Days'),
                  ('90_days','90 Days'),
                  ('180_days','180 Days'),
                  ('1_year','1 Year'),
                  ('2_years','2 Years'),
                  ('3_years','3 Years'),
                  ('4_years','4 Years'),
                  ('5_years','5 Years')], 'Duration', help="Duration of the Warranty"),
        'warranty_history':fields.one2many('mttl.warranty.history','serial_id', 'Warranty Claims History'),
        #+++ HoangTK - 02/18/2016 : Link warranty module to serials
        'warranty_ids': fields.one2many('warranty.cases','serial_id','Warranty Cases'),
        #Notes
        'notes':fields.text('Notes'),
        
        'image':fields.text('Images'),
        #attachments
        'attachment_lines': fields.one2many('ir.attachment', 'mttl_serials_id', 'Attachment'),
    }
    
    _defaults = {
        'serial_number':_generate_serial_number,
        'serial':'New Number',
    }
    
    
    
    def _check_sum(self, serial_no):
        weights=[8,7,6,5,4,3,2,0,10,9,8,7,6]
        weight_sum=0
        for i in range(0,13):
            x=serial_no[i:i+1]
            if x=="0":
                digit=0
            elif x=="1" or x=="A" or x=="J":
                digit=1
                
            elif x=="2" or x=="B" or x=="K" or x=="S":
                digit=2
        
            elif x=="3" or x=="C" or x=="L" or x=="T":
                digit=3
        
            elif x=="4" or x=="D" or x=="M" or x=="U":
                digit=4
        
            elif x=="5" or x=="E" or x=="N" or x=="V":
                digit=5
        
            elif x=="6" or x=="F" or x=="W":
                digit=6
        
            elif x=="7" or x=="G" or x=="P" or x=="X":
                digit=7
        
            elif x=="8" or x=="H" or x=="Y":
                digit=8
        
            elif x=="9" or x=="R" or x=="Z":
                digit=9
        
            elif x=="I" or x=="O" or x=="Q":
                return("?")
            else:
                return("?")
            
            weight_sum=weight_sum + (digit * weights[i])
                        
        check_digit = mod(weight_sum,11)
        check_digit="X" if check_digit == 10 else str(check_digit)
        return check_digit
            
    def generate_serial(self, cursor, user, ids, context=None):
        
        serial_obj=self.pool.get("mttl.serials")
        for serial in serial_obj.browse(cursor, user, ids, context=context):
            serial_no='M'
            
            # Adding year
            serial_no = serial_no + (serial.year.code)
            
            # Adding country
            serial_no = serial_no + (serial.country.code)
            
            # Adding Location
            serial_no = serial_no + (serial.location.code)
            
            # Adding Chassis 
            serial_no = serial_no + (serial.chassis.code)
            
            # Adding Model
            serial_no = serial_no + (serial.model.code)
            
            # Adding checksum and serial number
            serial_no = str(serial_no + 'X' + str(serial.serial_number))
            
            serial_no=serial_no.replace('X',self._check_sum(serial_no))
            
            serial_obj.write(cursor,user,ids,{'serial':serial_no})
