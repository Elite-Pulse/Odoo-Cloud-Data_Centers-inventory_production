# Datacenter Inventory for Odoo 19

Odoo 19 module **`cloud_inventory`**: a standalone datacenter equipment inventory for a Cloud department, fully separate from the ERP stock (no dependency on `stock`).

## Features
- **Location hierarchy:** Datacenter → Hall → Room → Rack (lanes A/B/C/D, 48 RU) → RU position, plus one warehouse per datacenter.
- **Three kinds of items:** physical (servers, switches...), digital (licenses, activation keys, with expiry) and logical.
- **Specifications:** brand, model, name, cluster, CPU, RAM, storage, NIC, HBA, service tag, TAG, site.
- **Life cycle:** In Warehouse → In Service → In Transit → Decommissioned. Each move is made through a wizard (reason, request/mail reference, replaced-by, comment) and logged in a movement history.
- **Rack generator:** creates racks per lane (e.g. `H1.4.A01` … `H1.4.A11`).
- **Dashboard:** counts by status, nature, datacenter, cluster, brand, product type and rack usage.
- **Reporting:** Excel and PDF export (detailed, summary, audit) with multi-term exact/partial search across every field, search-coverage table and movement history. Restricted to the Manager group.
- **Settings:** every list (brands, models, CPU, RAM, storage, NIC, HBA, clusters, sites, TAGs, types) is editable in-app.
- **Languages:** English and French, switchable per user from the *Language* menu.

## Install
1. Copy the `cloud_inventory` folder into your Odoo addons path.
2. Restart Odoo, enable developer mode, *Apps → Update Apps List*.
3. Install **Cloud Inventory** (or upgrade it). Requires Python package `xlsxwriter`.

## Security groups
| Group | Rights |
|---|---|
| Cloud Inventory / User | View, add and edit equipment, move equipment |
| Cloud Inventory / Manager (Settings and Export) | Settings, Excel/PDF export, audit search. Implied for Odoo administrators |

## Upgrade notes
Version 19.0.3.0.0 migrates the old "in stock / out" states to the new life-cycle states and racks from 42 to 48 RU.

## License
OPL-1 (Odoo Proprietary License v1.0), commercial module

## Author
Developed by **Abdechakour Hrouchan** — https://misterinfo.ma
