# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.constants import MOVE_TYPES, REASONS


class CloudInvMoveWizard(models.TransientModel):
    _name = 'cloud.inv.move.wizard'
    _description = 'Move equipment'

    asset_ids = fields.Many2many('cloud.inv.asset', string='Equipment')
    move_type = fields.Selection([m for m in MOVE_TYPES if m[0] != 'update'],
                                 string='Movement Type', required=True, default='deploy')
    reason = fields.Selection(REASONS, string='Reason')
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    request_ref = fields.Char(string='Request / Mail Reference')
    comment = fields.Text(string='Comment')
    replacement_id = fields.Many2one('cloud.inv.asset', string='Replaced By / Replacing')

    datacenter_id = fields.Many2one('cloud.inv.datacenter', string='Datacenter')
    warehouse_id = fields.Many2one('cloud.inv.warehouse', string='Warehouse',
                                   domain="[('datacenter_id', '=', datacenter_id)]")
    shelf = fields.Char(string='Shelf / Bin')
    hall_id = fields.Many2one('cloud.inv.hall', string='Hall',
                              domain="[('datacenter_id', '=', datacenter_id)]")
    room_id = fields.Many2one('cloud.inv.room', string='Room', domain="[('hall_id', '=', hall_id)]")
    rack_id = fields.Many2one('cloud.inv.rack', string='Rack', domain="[('room_id', '=', room_id)]")
    ru_start = fields.Integer(string='RU Start')
    ru_end = fields.Integer(string='RU End')
    destination_id = fields.Many2one('cloud.inv.site', string='Destination (other site)')

    @api.onchange('move_type')
    def _onchange_move_type(self):
        defaults = {'receive': 'received', 'deploy': 'new_request', 'return': 'replaced',
                    'transfer': 'reallocated', 'decommission': 'obsolete'}
        self.reason = defaults.get(self.move_type)
        asset = self.asset_ids[:1]
        if asset and not self.datacenter_id:
            self.datacenter_id = asset.datacenter_id

    @api.onchange('warehouse_id')
    def _onchange_warehouse(self):
        if self.warehouse_id:
            self.datacenter_id = self.warehouse_id.datacenter_id

    @api.onchange('rack_id')
    def _onchange_rack(self):
        if self.rack_id:
            self.room_id, self.hall_id = self.rack_id.room_id, self.rack_id.hall_id
            self.datacenter_id = self.rack_id.datacenter_id

    @api.onchange('room_id')
    def _onchange_room(self):
        if self.room_id:
            self.hall_id, self.datacenter_id = self.room_id.hall_id, self.room_id.datacenter_id
        if self.rack_id and self.rack_id.room_id != self.room_id:
            self.rack_id = False

    @api.onchange('hall_id')
    def _onchange_hall(self):
        if self.hall_id:
            self.datacenter_id = self.hall_id.datacenter_id
        if self.room_id and self.room_id.hall_id != self.hall_id:
            self.room_id = self.rack_id = False

    def action_confirm(self):
        self.ensure_one()
        if not self.asset_ids:
            raise UserError(_('Select at least one item.'))
        t = self.move_type
        vals = {'last_reason': self.reason, 'request_ref': self.request_ref or False}
        if t in ('receive', 'return'):
            if not self.warehouse_id:
                raise UserError(_('Select the destination warehouse.'))
            vals.update(state='in_warehouse', datacenter_id=self.datacenter_id.id,
                        warehouse_id=self.warehouse_id.id, shelf=self.shelf,
                        hall_id=False, room_id=False, rack_id=False, ru_start=0, ru_end=0,
                        destination_id=False, date_out=False)
            if t == 'receive':
                vals['date_in'] = self.date
        elif t in ('deploy', 'relocate'):
            if not self.rack_id:
                raise UserError(_('Select the destination rack.'))
            if len(self.asset_ids) > 1 and self.ru_start:
                raise UserError(_('Set the RU position for one item at a time.'))
            vals.update(state='in_service', datacenter_id=self.datacenter_id.id,
                        hall_id=self.hall_id.id, room_id=self.room_id.id, rack_id=self.rack_id.id,
                        ru_start=self.ru_start, ru_end=self.ru_end or self.ru_start,
                        warehouse_id=False, shelf=False, destination_id=False)
            if t == 'deploy':
                vals['date_out'] = self.date
        elif t == 'transfer':
            if not self.destination_id:
                raise UserError(_('Select the destination site.'))
            vals.update(state='in_transit', destination_id=self.destination_id.id,
                        hall_id=False, room_id=False, rack_id=False, ru_start=0, ru_end=0,
                        warehouse_id=False, shelf=False, date_out=self.date)
        elif t == 'decommission':
            vals.update(state='decommissioned', hall_id=False, room_id=False, rack_id=False,
                        ru_start=0, ru_end=0, date_out=self.date)
            if self.warehouse_id:
                vals.update(warehouse_id=self.warehouse_id.id, datacenter_id=self.datacenter_id.id,
                            shelf=self.shelf)
        Move = self.env['cloud.inv.movement']
        for asset in self.asset_ids:
            before = asset._location_label()
            # free the old position first to avoid RU overlap with itself
            asset.with_context(cloud_inv_no_log=True).write(vals)
            Move.create({
                'asset_id': asset.id, 'move_type': t,
                'date': fields.Datetime.now(),
                'from_location': before, 'to_location': asset._location_label(),
                'reason': self.reason, 'replacement_id': self.replacement_id.id,
                'request_ref': self.request_ref, 'comment': self.comment,
            })
            if self.comment:
                asset.message_post(body=_('%(type)s — %(comment)s') % {
                    'type': dict(MOVE_TYPES).get(t), 'comment': self.comment})
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}
