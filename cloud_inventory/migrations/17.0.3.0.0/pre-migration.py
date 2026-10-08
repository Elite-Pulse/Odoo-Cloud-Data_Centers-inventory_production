# -*- coding: utf-8 -*-
def migrate(cr, version):
    """v2 -> v3: remap the old stock states and rack size."""
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name='cloud_inv_asset' AND column_name='state'")
    if cr.fetchone():
        # old 'out' -> in service (it was used somewhere) ; old 'in_stock' -> in service if mounted, else warehouse
        cr.execute("UPDATE cloud_inv_asset SET state='in_service' WHERE state='out'")
        cr.execute("UPDATE cloud_inv_asset SET state='in_service' WHERE state='in_stock' AND rack_id IS NOT NULL")
        cr.execute("UPDATE cloud_inv_asset SET state='in_warehouse' WHERE state='in_stock'")
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name='cloud_inv_rack' AND column_name='total_ru'")
    if cr.fetchone():
        cr.execute("UPDATE cloud_inv_rack SET total_ru=48 WHERE total_ru=42")
