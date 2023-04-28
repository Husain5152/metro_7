import openerp.addons.decimal_precision as dp
from osv import fields,osv

class MetroSupplierProductInfo(osv.osv):
    _inherit = "product.supplierinfo"

    _columns={
        'currency':fields.many2one('res.currency','Currency',),
    }
    
    def get_currency(self, cursor, user, ids, supplier_id, context={}):
        """
        Method to get currency from supplier's pricelist
        """
        partner_obj = self.pool.get('res.partner')
        pricelist_obj = self.pool.get('product.pricelist')
        res={}        
        print partner_obj.browse(cursor, user, supplier_id, 
            context=context)
        supplier = partner_obj.browse(cursor, user, supplier_id, 
            context=context)
        pricelist_id = supplier.property_product_pricelist_purchase.id
        if pricelist_id:
            currency_id = pricelist_obj.browse(cursor, user, 
                pricelist_id).currency_id.id                           
        return {'value':{'currency':currency_id}}
