# -*- coding: utf-8 -*-
"""Shared selection lists (lifecycle vocabulary of the Cloud department)."""

# Where an item is in its life: received -> warehouse -> service -> warehouse / transit / decommissioned
STATES = [
    ('in_warehouse', 'In Warehouse'),
    ('in_service', 'In Service'),
    ('in_transit', 'In Transit'),
    ('decommissioned', 'Decommissioned'),
]

# Why an item moved or changed status
REASONS = [
    ('received', 'Received (new equipment)'),
    ('new_request', 'New request / project'),
    ('replaced', 'Replaced'),
    ('obsolete', 'Obsolete'),
    ('deprecated', 'Deprecated (end of life)'),
    ('upgraded', 'Upgraded'),
    ('faulty', 'Faulty / failed'),
    ('reallocated', 'Reallocated (on request)'),
    ('surplus', 'Surplus / no longer needed'),
    ('other', 'Other'),
]

MOVE_TYPES = [
    ('receive', 'Receipt in warehouse'),
    ('deploy', 'Deployment (put in service)'),
    ('relocate', 'Relocation'),
    ('return', 'Return to warehouse'),
    ('transfer', 'Transfer / shipment to another site'),
    ('decommission', 'Decommissioning'),
    ('update', 'Manual update'),
]

LANES = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]
