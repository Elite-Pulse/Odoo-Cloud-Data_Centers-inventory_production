# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from .constants import LANES


class CloudInvDatacenter(models.Model):
    _name = 'cloud.inv.datacenter'
    _description = 'Datacenter'
    _order = 'name'

    name = fields.Char(string='Datacenter', required=True)
    code = fields.Char(string='Code', required=True,
                       help='Short code, e.g. CDC (Casa) or BDC (Benguerir)')
    city = fields.Char(string='City')
    color = fields.Integer(string='Color')
    active = fields.Boolean(string='Active', default=True)
    note = fields.Text(string='Notes')
    hall_ids = fields.One2many('cloud.inv.hall', 'datacenter_id', string='Halls')
    hall_count = fields.Integer(string='Hall Count', compute='_compute_counts')
    asset_count = fields.Integer(string='Product Count', compute='_compute_counts')

    _sql_constraints = [('code_uniq', 'unique(code)', 'Datacenter code must be unique.')]

    def _compute_counts(self):
        Asset = self.env['cloud.inv.asset']
        for rec in self:
            rec.hall_count = len(rec.hall_ids)
            rec.asset_count = Asset.search_count([('datacenter_id', '=', rec.id)])

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '[%s] %s' % (r.code or '', r.name or '')

    def action_view_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.name,
            'res_model': 'cloud.inv.asset', 'view_mode': 'tree,kanban,form',
            'domain': [('datacenter_id', '=', self.id)],
            'context': {'default_datacenter_id': self.id},
        }


class CloudInvWarehouse(models.Model):
    """Warehouse of a datacenter: where received / unused equipment is kept."""
    _name = 'cloud.inv.warehouse'
    _description = 'Warehouse'
    _order = 'datacenter_id, name'

    name = fields.Char(string='Warehouse', required=True)
    datacenter_id = fields.Many2one('cloud.inv.datacenter', string='Datacenter',
                                    required=True, ondelete='restrict')
    active = fields.Boolean(string='Active', default=True)
    note = fields.Text(string='Notes')
    asset_count = fields.Integer(string='Items in Warehouse', compute='_compute_asset_count')

    @api.depends('name', 'datacenter_id.code')
    def _compute_display_name(self):
        for r in self:
            r.display_name = '%s / %s' % (r.datacenter_id.code or '', r.name or '')

    def _compute_asset_count(self):
        Asset = self.env['cloud.inv.asset']
        for rec in self:
            rec.asset_count = Asset.search_count(
                [('warehouse_id', '=', rec.id), ('state', '=', 'in_warehouse')])

    def action_view_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': self.display_name,
            'res_model': 'cloud.inv.asset', 'view_mode': 'tree,kanban,form',
            'domain': [('warehouse_id', '=', self.id), ('state', '=', 'in_warehouse')],
            'context': {'default_warehouse_id': self.id, 'default_datacenter_id': self.datacenter_id.id},
        }


class CloudInvHall(models.Model):
    _name = 'cloud.inv.hall'
    _rec_name = 'complete_name'
    _description = 'Data Hall'
    _order = 'complete_name'

    name = fields.Char(string='Hall', required=True)
    datacenter_id = fields.Many2one('cloud.inv.datacenter', string='Datacenter',
                                    required=True, ondelete='restrict')
    complete_name = fields.Char(string='Complete Name', compute='_compute_complete_name', store=True)
    room_ids = fields.One2many('cloud.inv.room', 'hall_id', string='Rooms')
    note = fields.Text(string='Notes')

    @api.depends('name', 'datacenter_id.code')
    def _compute_complete_name(self):
        for rec in self:
            rec.complete_name = '%s / %s' % (rec.datacenter_id.code or '', rec.name or '')


class CloudInvRoom(models.Model):
    _name = 'cloud.inv.room'
    _rec_name = 'complete_name'
    _description = 'Room'
    _order = 'complete_name'

    name = fields.Char(string='Room', required=True)
    hall_id = fields.Many2one('cloud.inv.hall', string='Hall', required=True, ondelete='restrict')
    datacenter_id = fields.Many2one(related='hall_id.datacenter_id', store=True, string='Datacenter')
    complete_name = fields.Char(string='Complete Name', compute='_compute_complete_name', store=True)
    rack_ids = fields.One2many('cloud.inv.rack', 'room_id', string='Racks')
    note = fields.Text(string='Notes')

    @api.depends('name', 'hall_id.complete_name')
    def _compute_complete_name(self):
        for rec in self:
            rec.complete_name = '%s / %s' % (rec.hall_id.complete_name or '', rec.name or '')

    def action_generate_racks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Racks'),
            'res_model': 'cloud.inv.rack.generator',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_room_id': self.id},
        }


class CloudInvRack(models.Model):
    _name = 'cloud.inv.rack'
    _rec_name = 'complete_name'
    _description = 'Rack'
    _order = 'complete_name'

    name = fields.Char(string='Rack', required=True)
    room_id = fields.Many2one('cloud.inv.room', string='Room', required=True, ondelete='restrict')
    hall_id = fields.Many2one(related='room_id.hall_id', store=True, string='Hall')
    datacenter_id = fields.Many2one(related='room_id.datacenter_id', store=True, string='Datacenter')
    complete_name = fields.Char(string='Complete Name', compute='_compute_complete_name', store=True)
    lane = fields.Selection(LANES, string='Lane')
    number = fields.Integer(string='Position in Lane')
    total_ru = fields.Integer(string='Total RU', default=48)
    used_ru = fields.Integer(string='Used RU', compute='_compute_usage')
    free_ru = fields.Integer(string='Free RU', compute='_compute_usage')
    usage_percent = fields.Float(string='Usage %', compute='_compute_usage')
    asset_ids = fields.One2many('cloud.inv.asset', 'rack_id', string='Equipment')
    note = fields.Text(string='Notes')

    @api.depends('name', 'room_id.complete_name')
    def _compute_complete_name(self):
        for rec in self:
            rec.complete_name = '%s / %s' % (rec.room_id.complete_name or '', rec.name or '')

    def _compute_usage(self):
        Asset = self.env['cloud.inv.asset']
        for rec in self:
            assets = Asset.search([('rack_id', '=', rec.id), ('state', '=', 'in_service'), ('ru_start', '>', 0)])
            used = sum((a.ru_end or a.ru_start) - a.ru_start + 1 for a in assets)
            rec.used_ru = used
            rec.free_ru = max(rec.total_ru - used, 0)
            rec.usage_percent = (used * 100.0 / rec.total_ru) if rec.total_ru else 0.0
