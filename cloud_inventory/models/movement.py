# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .constants import MOVE_TYPES, REASONS


class CloudInvMovement(models.Model):
    """Traceability of every location / status change of an item."""
    _name = 'cloud.inv.movement'
    _description = 'Equipment Movement'
    _order = 'date desc, id desc'

    asset_id = fields.Many2one('cloud.inv.asset', string='Equipment', required=True,
                               ondelete='cascade', index=True)
    asset_nature = fields.Selection(related='asset_id.nature', string='Nature', store=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now, required=True)
    move_type = fields.Selection(MOVE_TYPES, string='Movement Type', required=True)
    from_location = fields.Char(string='From')
    to_location = fields.Char(string='To')
    reason = fields.Selection(REASONS, string='Reason')
    replacement_id = fields.Many2one('cloud.inv.asset', string='Replaced By / Replacing',
                                     ondelete='set null')
    request_ref = fields.Char(string='Request / Mail Reference')
    comment = fields.Text(string='Comment')
    user_id = fields.Many2one('res.users', string='Done By', default=lambda s: s.env.user,
                              required=True)

    def write(self, vals):
        if not self.env.su and not self.env.user.has_group('cloud_inventory.group_cloud_inv_manager'):
            raise UserError(_('Movement history cannot be modified.'))
        return super().write(vals)

    def unlink(self):
        if (not self.env.su and not self.env.context.get('cloud_inv_cascade')
                and not self.env.user.has_group('cloud_inventory.group_cloud_inv_manager')):
            raise UserError(_('Movement history cannot be deleted.'))
        return super().unlink()
