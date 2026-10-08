# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class CloudInvRackGenerator(models.TransientModel):
    """Create the racks of a room by lane: H1.4.A01 ... H1.4.A11."""
    _name = 'cloud.inv.rack.generator'
    _description = 'Rack generator'

    room_id = fields.Many2one('cloud.inv.room', string='Room', required=True)
    prefix = fields.Char(string='Prefix', required=True,
                         help='Example: H1.4 gives racks H1.4.A01, H1.4.A02 ...')
    lanes = fields.Char(string='Lanes', default='A,B,C,D', required=True,
                        help='Comma separated lane letters')
    racks_per_lane = fields.Integer(string='Racks per Lane', default=11, required=True)
    total_ru = fields.Integer(string='RU per Rack', default=48, required=True)
    padding = fields.Integer(string='Number Digits', default=2)

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        room = self.env['cloud.inv.room'].browse(res.get('room_id'))
        if room and 'prefix' in fields_list:
            h = ''.join(c for c in (room.hall_id.name or '') if c.isdigit())
            r = ''.join(c for c in (room.name or '') if c.isdigit())
            res['prefix'] = 'H%s.%s' % (h or '?', r or '?')
        return res

    def action_generate(self):
        self.ensure_one()
        lanes = [l.strip().upper() for l in self.lanes.split(',') if l.strip()]
        if not lanes or self.racks_per_lane < 1:
            raise UserError(_('Define at least one lane and one rack per lane.'))
        Rack = self.env['cloud.inv.rack']
        existing = set(Rack.search([('room_id', '=', self.room_id.id)]).mapped('name'))
        vals = []
        for lane in lanes:
            if lane not in dict(Rack._fields['lane'].selection):
                raise UserError(_('Unknown lane "%s". Use A, B, C or D.') % lane)
            for n in range(1, self.racks_per_lane + 1):
                name = '%s.%s%s' % (self.prefix, lane, str(n).zfill(self.padding))
                if name not in existing:
                    vals.append({'name': name, 'room_id': self.room_id.id, 'lane': lane,
                                 'number': n, 'total_ru': self.total_ru})
        Rack.create(vals)
        return {
            'type': 'ir.actions.act_window', 'name': _('Racks'), 'res_model': 'cloud.inv.rack',
            'view_mode': 'tree,form', 'domain': [('room_id', '=', self.room_id.id)],
        }
