# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .constants import REASONS, STATES

MANAGER_GROUP = 'cloud_inventory.group_cloud_inv_manager'

# Fields whose change is a "movement" and is logged automatically
LOC_FIELDS = ('state', 'datacenter_id', 'hall_id', 'room_id', 'rack_id', 'ru_start',
              'ru_end', 'warehouse_id', 'shelf', 'destination_id')


class CloudInvAsset(models.Model):
    _name = 'cloud.inv.asset'
    _description = 'Cloud Inventory Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_in desc, id desc'

    name = fields.Char(string='Name', required=True, tracking=True)
    reference = fields.Char(string='Reference', readonly=True, copy=False, default='/')
    nature = fields.Selection([
        ('physical', 'Physical'),
        ('digital', 'Digital (license / key)'),
        ('logical', 'Logical'),
    ], string='Nature', required=True, default='physical', tracking=True)
    product_type_id = fields.Many2one('cloud.inv.product.type', string='Product Type', tracking=True)

    brand_id = fields.Many2one('cloud.inv.brand', string='Brand', tracking=True)
    model_id = fields.Many2one('cloud.inv.model', string='Model',
                               domain="[('brand_id', 'in', (brand_id, False))]", tracking=True)
    cluster_id = fields.Many2one('cloud.inv.cluster', string='Cluster', tracking=True)
    cpu_id = fields.Many2one('cloud.inv.cpu', string='CPU')
    ram_id = fields.Many2one('cloud.inv.ram', string='RAM')
    storage_id = fields.Many2one('cloud.inv.storage', string='Storage')
    nic_ids = fields.Many2many('cloud.inv.nic', 'cloud_inv_asset_nic_rel', 'asset_id', 'nic_id',
                               string='NIC')
    hba_ids = fields.Many2many('cloud.inv.hba', 'cloud_inv_asset_hba_rel', 'asset_id', 'hba_id',
                               string='HBA')
    service_tag = fields.Char(string='Service Tag', tracking=True)
    tag_id = fields.Many2one('cloud.inv.tag', string='TAG', tracking=True)
    site_id = fields.Many2one('cloud.inv.site', string='Site')

    # Location
    datacenter_id = fields.Many2one('cloud.inv.datacenter', string='Datacenter', tracking=True)
    warehouse_id = fields.Many2one('cloud.inv.warehouse', string='Warehouse',
                                   domain="[('datacenter_id', '=', datacenter_id)]", tracking=True)
    shelf = fields.Char(string='Shelf / Bin')
    hall_id = fields.Many2one('cloud.inv.hall', string='Hall',
                              domain="[('datacenter_id', '=', datacenter_id)]", tracking=True)
    room_id = fields.Many2one('cloud.inv.room', string='Room',
                              domain="[('hall_id', '=', hall_id)]", tracking=True)
    rack_id = fields.Many2one('cloud.inv.rack', string='Rack',
                              domain="[('room_id', '=', room_id)]", tracking=True)
    rack_lane = fields.Selection(related='rack_id.lane', string='Lane', store=True)
    ru_start = fields.Integer(string='RU Start')
    ru_end = fields.Integer(string='RU End')
    ru_display = fields.Char(string='RU', compute='_compute_ru_display', store=True)
    destination_id = fields.Many2one('cloud.inv.site', string='Destination (other site)',
                                     tracking=True)
    request_ref = fields.Char(string='Request / Mail Reference')

    # Digital
    license_key = fields.Char(string='License / Key', groups='cloud_inventory.group_cloud_inv_user')
    license_expiry = fields.Date(string='Expiry Date', tracking=True)
    license_seats = fields.Integer(string='Seats / Cores')

    # Lifecycle
    state = fields.Selection(STATES, string='Status', default='in_warehouse', required=True,
                             tracking=True)
    last_reason = fields.Selection(REASONS, string='Last Reason', tracking=True)
    date_in = fields.Date(string='Warehouse Entry Date', default=fields.Date.context_today,
                          tracking=True)
    date_out = fields.Date(string='Warehouse Exit Date', tracking=True)
    responsible_id = fields.Many2one('res.users', string='Responsible',
                                     default=lambda s: s.env.user, tracking=True)
    comment = fields.Text(string='Comment')
    move_ids = fields.One2many('cloud.inv.movement', 'asset_id', string='Movement History')
    move_count = fields.Integer(string='Movements', compute='_compute_move_count')

    @api.depends('move_ids')
    def _compute_move_count(self):
        for rec in self:
            rec.move_count = len(rec.move_ids)

    @api.depends('ru_start', 'ru_end')
    def _compute_ru_display(self):
        for rec in self:
            if rec.ru_start and rec.ru_end and rec.ru_end != rec.ru_start:
                rec.ru_display = '%s-%s' % (rec.ru_start, rec.ru_end)
            elif rec.ru_start:
                rec.ru_display = str(rec.ru_start)
            else:
                rec.ru_display = False

    # ---- location label (used by movement log, reports) ----
    def _location_label(self):
        self.ensure_one()
        state_label = dict(self._fields['state']._description_selection(self.env)).get(self.state, '')
        if self.state == 'in_service':
            parts = [self.datacenter_id.code, self.hall_id.name, self.room_id.name]
            if self.rack_id:
                parts.append(self.rack_id.name)
            if self.ru_display:
                parts.append('RU %s' % self.ru_display)
            where = ' / '.join(p for p in parts if p)
        elif self.state == 'in_warehouse':
            where = self.warehouse_id.display_name or self.datacenter_id.code or ''
            if self.shelf:
                where = '%s (%s)' % (where, self.shelf)
        elif self.state == 'in_transit':
            where = self.destination_id.name or ''
        else:
            where = self.warehouse_id.display_name or self.datacenter_id.code or ''
        return '%s: %s' % (state_label, where) if where else state_label

    # ---- location cascade ----
    @api.onchange('warehouse_id')
    def _onchange_warehouse(self):
        if self.warehouse_id:
            self.datacenter_id = self.warehouse_id.datacenter_id

    @api.onchange('rack_id')
    def _onchange_rack(self):
        if self.rack_id:
            self.room_id = self.rack_id.room_id
            self.hall_id = self.rack_id.hall_id
            self.datacenter_id = self.rack_id.datacenter_id

    @api.onchange('room_id')
    def _onchange_room(self):
        if self.room_id:
            self.hall_id = self.room_id.hall_id
            self.datacenter_id = self.room_id.datacenter_id
        if self.rack_id and self.rack_id.room_id != self.room_id:
            self.rack_id = False

    @api.onchange('hall_id')
    def _onchange_hall(self):
        if self.hall_id:
            self.datacenter_id = self.hall_id.datacenter_id
        if self.room_id and self.room_id.hall_id != self.hall_id:
            self.room_id = False
            self.rack_id = False

    @api.onchange('datacenter_id')
    def _onchange_datacenter(self):
        if self.hall_id and self.hall_id.datacenter_id != self.datacenter_id:
            self.hall_id = False
            self.room_id = False
            self.rack_id = False
        if self.warehouse_id and self.warehouse_id.datacenter_id != self.datacenter_id:
            self.warehouse_id = False

    @api.onchange('brand_id')
    def _onchange_brand(self):
        if self.model_id and self.model_id.brand_id and self.model_id.brand_id != self.brand_id:
            self.model_id = False

    @api.onchange('model_id')
    def _onchange_model(self):
        if self.model_id.brand_id:
            self.brand_id = self.model_id.brand_id

    @api.onchange('product_type_id')
    def _onchange_product_type(self):
        if self.product_type_id.nature:
            self.nature = self.product_type_id.nature

    # ---- constraints ----
    @api.constrains('rack_id', 'room_id', 'hall_id', 'datacenter_id', 'warehouse_id')
    def _check_location_consistency(self):
        for rec in self:
            if rec.rack_id and rec.room_id and rec.rack_id.room_id != rec.room_id:
                raise ValidationError(_('The rack does not belong to the selected room.'))
            if rec.room_id and rec.hall_id and rec.room_id.hall_id != rec.hall_id:
                raise ValidationError(_('The room does not belong to the selected hall.'))
            if rec.hall_id and rec.datacenter_id and rec.hall_id.datacenter_id != rec.datacenter_id:
                raise ValidationError(_('The hall does not belong to the selected datacenter.'))
            if rec.warehouse_id and rec.datacenter_id and rec.warehouse_id.datacenter_id != rec.datacenter_id:
                raise ValidationError(_('The warehouse does not belong to the selected datacenter.'))

    @api.constrains('rack_id', 'ru_start', 'ru_end', 'state')
    def _check_rack_units(self):
        for rec in self:
            if rec.state != 'in_service' or not rec.rack_id or not rec.ru_start:
                continue
            start, end = rec.ru_start, (rec.ru_end or rec.ru_start)
            if start < 1 or end < start or (rec.rack_id.total_ru and end > rec.rack_id.total_ru):
                raise ValidationError(_('Invalid RU range %s-%s for rack %s (%s RU).') % (
                    start, end, rec.rack_id.name, rec.rack_id.total_ru))
            clash = self.search([
                ('id', '!=', rec.id), ('rack_id', '=', rec.rack_id.id), ('state', '=', 'in_service'),
                ('ru_start', '>', 0), ('ru_start', '<=', end)]).filtered(
                lambda a: (a.ru_end or a.ru_start) >= start)
            if clash:
                raise ValidationError(_('RU %s-%s in rack %s already used by: %s') % (
                    start, end, rec.rack_id.name, ', '.join(clash.mapped('name'))))

    @api.constrains('date_in', 'date_out')
    def _check_dates(self):
        for rec in self:
            if rec.date_in and rec.date_out and rec.date_out < rec.date_in:
                raise ValidationError(_('The exit date cannot be before the entry date.'))

    # ---- CRUD ----
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference') or vals.get('reference') == '/':
                vals['reference'] = self.env['ir.sequence'].next_by_code('cloud.inv.asset') or '/'
        records = super().create(vals_list)
        if not self.env.context.get('cloud_inv_no_log'):
            Move = self.env['cloud.inv.movement']
            for rec in records:
                Move.create({
                    'asset_id': rec.id, 'move_type': 'receive',
                    'from_location': _('New'), 'to_location': rec._location_label(),
                    'reason': 'received', 'request_ref': rec.request_ref,
                })
        return records

    def write(self, vals):
        if self.env.context.get('cloud_inv_no_log') or not (set(vals) & set(LOC_FIELDS)):
            return super().write(vals)
        before = {r.id: r._location_label() for r in self}
        res = super().write(vals)
        Move = self.env['cloud.inv.movement']
        for rec in self:
            after = rec._location_label()
            if after != before[rec.id]:
                Move.create({
                    'asset_id': rec.id, 'move_type': 'update',
                    'from_location': before[rec.id], 'to_location': after,
                    'reason': vals.get('last_reason') or rec.last_reason,
                    'request_ref': rec.request_ref,
                })
        return res

    @api.depends('name', 'reference')
    def _compute_display_name(self):
        for r in self:
            if r.reference and r.reference != '/':
                r.display_name = '[%s] %s' % (r.reference, r.name or '')
            else:
                r.display_name = r.name or ''

    # ---- lifecycle actions (open the movement wizard) ----
    def _open_move_wizard(self, move_type):
        return {
            'type': 'ir.actions.act_window',
            'name': dict(self.env['cloud.inv.movement']._fields['move_type']
                         ._description_selection(self.env)).get(move_type),
            'res_model': 'cloud.inv.move.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_ids': [(6, 0, self.ids)], 'default_move_type': move_type},
        }

    def action_receive(self):
        return self._open_move_wizard('receive')

    def action_deploy(self):
        return self._open_move_wizard('deploy')

    def action_relocate(self):
        return self._open_move_wizard('relocate')

    def action_return(self):
        return self._open_move_wizard('return')

    def action_transfer(self):
        return self._open_move_wizard('transfer')

    def action_decommission(self):
        return self._open_move_wizard('decommission')

    def action_view_movements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Movements'),
            'res_model': 'cloud.inv.movement', 'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
        }

    # ---- export (managers and administrators only) ----
    def _check_export_rights(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_('Only Cloud Inventory managers and administrators can export data.'))

    def _selection_wizard(self):
        self._check_export_rights()
        return self.env['cloud.inv.report.wizard'].create({'asset_ids': [(6, 0, self.ids)]})

    def action_export_selected(self):
        """Bound to the list view: open the export wizard on the selection."""
        self._check_export_rights()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Export selection'),
            'res_model': 'cloud.inv.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_ids': [(6, 0, self.ids)]},
        }

    def action_export_xlsx_selected(self):
        return self._selection_wizard().action_export_xlsx()

    def action_print_pdf_selected(self):
        return self._selection_wizard().action_print_pdf()

    # ---- language switch (FR / EN) ----
    @api.model
    def action_switch_lang(self, code):
        Lang = self.env['res.lang'].sudo()
        if not Lang.with_context(active_test=False).search([('code', '=', code)], limit=1):
            raise UserError(_('Unknown language %s.') % code)
        if not Lang.search([('code', '=', code)], limit=1):
            # activate the language and load its translations on the fly
            Lang._activate_lang(code)
            self.env['ir.module.module'].sudo().search([('state', '=', 'installed')])._update_translations([code])
        self.env.user.sudo().write({'lang': code})
        return {'type': 'ir.actions.client', 'tag': 'reload_context'}
