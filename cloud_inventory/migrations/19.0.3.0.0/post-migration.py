# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Assign existing warehouse items to their datacenter warehouse and derive rack lanes."""
    cr.execute("""
        UPDATE cloud_inv_asset a SET warehouse_id = w.id
        FROM cloud_inv_warehouse w
        WHERE a.state='in_warehouse' AND a.warehouse_id IS NULL AND w.datacenter_id = a.datacenter_id
    """)
    # racks named like H1.4.A01 / H1R1A4 : lane = the letter A-D followed by digits at the end
    cr.execute("""
        UPDATE cloud_inv_rack SET lane = upper(substring(name from '([A-Da-d])[0-9]+$')),
               number = substring(name from '[0-9]+$')::int
        WHERE lane IS NULL AND name ~ '[A-Da-d][0-9]+$'
    """)
