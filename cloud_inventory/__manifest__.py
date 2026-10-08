# -*- coding: utf-8 -*-
{
    'name': 'Datacenter Inventory (Cloud Inventory)',
    'version': '19.0.3.0.0',
    'category': 'Inventory/Cloud',
    'summary': 'Cloud datacenter inventory: servers, licenses, logical assets, racks, audit reporting (FR / EN)',
    'description': """
Cloud Inventory
===============
Standalone inventory for the Cloud department (independent from the ERP stock module).

* Datacenter > Hall > Room > Rack > RU location hierarchy
* Physical, digital (licenses, activation keys) and logical assets
* Equipment life cycle: warehouse, in service, in transit, decommissioned, with movement history and reasons
* Racks organised by lane (A/B/C/D), 48 RU, NIC / HBA specifications
* Responsible, comments, chatter
* Global dashboard
* Advanced search and filters
* Excel and PDF reporting (managers / administrators): detailed, summary and audit reports
  with multi-term search across every field
* Configurable lists (brands, models, CPU, RAM, storage, clusters, sites, tags, types)
* French and English
    """,
    'author': 'Abdechakour Hrouchan',
    'maintainer': 'Abdechakour Hrouchan',
    'website': 'https://misterinfo.ma',
    'support': 'https://misterinfo.ma',
    'images': ['static/description/banner.png'],
    'price': 274.99,
    'currency': 'USD',
    'external_dependencies': {'python': ['xlsxwriter']},
    'depends': ['base', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/seed_data.xml',
        'views/location_views.xml',
        'views/config_views.xml',
        'views/asset_views.xml',
        'views/movement_views.xml',
        'views/dashboard_views.xml',
        'report/report_assets.xml',
        'wizard/report_wizard_views.xml',
        'wizard/move_wizard_views.xml',
        'wizard/rack_generator_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'OPL-1',
}
