# -*- coding: utf-8 -*-
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, fields, models


class CloudInvDashboard(models.Model):
    _name = 'cloud.inv.dashboard'
    _description = 'Cloud Inventory Dashboard'

    total = fields.Integer(string='Total Products', compute='_compute_kpis')
    in_warehouse = fields.Integer(string='In Warehouse', compute='_compute_kpis')
    in_service = fields.Integer(string='In Service', compute='_compute_kpis')
    in_transit = fields.Integer(string='In Transit', compute='_compute_kpis')
    decommissioned = fields.Integer(string='Decommissioned', compute='_compute_kpis')
    physical = fields.Integer(string='Physical', compute='_compute_kpis')
    digital = fields.Integer(string='Digital', compute='_compute_kpis')
    logical = fields.Integer(string='Logical', compute='_compute_kpis')
    expiring = fields.Integer(string='Expiring Soon', compute='_compute_kpis')
    expired = fields.Integer(string='Expired', compute='_compute_kpis')
    html_datacenter = fields.Html(string='By Datacenter', compute='_compute_tables', sanitize=False)
    html_type = fields.Html(string='By Product Type', compute='_compute_tables', sanitize=False)
    html_brand = fields.Html(string='By Brand', compute='_compute_tables', sanitize=False)
    html_cluster = fields.Html(string='By Cluster', compute='_compute_tables', sanitize=False)
    html_state = fields.Html(string='By Status', compute='_compute_tables', sanitize=False)
    html_racks = fields.Html(string='Rack Usage', compute='_compute_tables', sanitize=False)

    # ---------- helpers ----------
    def _expiring_domain(self):
        today = fields.Date.context_today(self)
        return [('nature', '=', 'digital'), ('state', '!=', 'decommissioned'),
                ('license_expiry', '>=', today), ('license_expiry', '<=', today + timedelta(days=30))]

    def _expired_domain(self):
        return [('nature', '=', 'digital'), ('state', '!=', 'decommissioned'),
                ('license_expiry', '<', fields.Date.context_today(self))]

    def _compute_kpis(self):
        A = self.env['cloud.inv.asset']
        for rec in self:
            rec.total = A.search_count([])
            rec.in_warehouse = A.search_count([('state', '=', 'in_warehouse')])
            rec.in_service = A.search_count([('state', '=', 'in_service')])
            rec.in_transit = A.search_count([('state', '=', 'in_transit')])
            rec.decommissioned = A.search_count([('state', '=', 'decommissioned')])
            rec.physical = A.search_count([('nature', '=', 'physical')])
            rec.digital = A.search_count([('nature', '=', 'digital')])
            rec.logical = A.search_count([('nature', '=', 'logical')])
            rec.expiring = A.search_count(self._expiring_domain())
            rec.expired = A.search_count(self._expired_domain())

    def _bar_table(self, title, rows, color):
        """rows: list of (label, count)."""
        top = max([c for _l, c in rows] or [1]) or 1
        body = Markup('')
        for label, count in rows:
            pct = int(count * 100 / top)
            body += Markup(
                '<tr><td style="padding:4px 10px 4px 0;white-space:nowrap">%s</td>'
                '<td style="width:100%%"><div style="background:#eef0f4;border-radius:6px;height:14px">'
                '<div style="width:%s%%;background:%s;height:14px;border-radius:6px"></div></div></td>'
                '<td style="padding-left:10px;text-align:right"><b>%s</b></td></tr>'
            ) % (escape(label), pct, color, count)
        if not rows:
            body = Markup('<tr><td class="text-muted">%s</td></tr>') % _('No data')
        return Markup('<h5 style="margin:0 0 8px">%s</h5><table style="width:100%%">%s</table>') % (title, body)

    def _group_rows(self, field):
        res = self.env['cloud.inv.asset'].read_group([], [field], [field])
        rows = []
        for r in res:
            val = r[field]
            label = val[1] if val else _('Undefined')
            rows.append((label, r.get('__count', r.get(field + '_count', 0))))
        rows.sort(key=lambda x: -x[1])
        return rows

    def _compute_tables(self):
        for rec in self:
            labels = dict(self.env['cloud.inv.asset']._fields['state']._description_selection(self.env))
            srows = [(labels[k], self.env['cloud.inv.asset'].search_count([('state', '=', k)])) for k in labels]
            rec.html_state = rec._bar_table(_('By Status'), srows, '#28A745')
            rec.html_cluster = rec._bar_table(_('By Cluster'), rec._group_rows('cluster_id'), '#6F42C1')
            rec.html_datacenter = rec._bar_table(_('By Datacenter'), rec._group_rows('datacenter_id'), '#714B67')
            rec.html_type = rec._bar_table(_('By Product Type'), rec._group_rows('product_type_id'), '#017E84')
            rec.html_brand = rec._bar_table(_('By Brand'), rec._group_rows('brand_id')[:10], '#F06050')
            racks = self.env['cloud.inv.rack'].search([])
            racks = sorted(racks, key=lambda r: -r.usage_percent)[:10]
            rows = [('%s (%s/%s RU)' % (r.complete_name, r.used_ru, r.total_ru), int(r.usage_percent))
                    for r in racks]
            rec.html_racks = rec._bar_table(_('Rack Usage (%)'), rows, '#F4A460')

    # ---------- actions ----------
    def _open_assets(self, name, domain):
        return {
            'type': 'ir.actions.act_window', 'name': name, 'res_model': 'cloud.inv.asset',
            'view_mode': 'list,kanban,form,pivot,graph', 'domain': domain,
        }

    def action_total(self):
        return self._open_assets(_('All Products'), [])

    def action_in_warehouse(self):
        return self._open_assets(_('In Warehouse'), [('state', '=', 'in_warehouse')])

    def action_in_service(self):
        return self._open_assets(_('In Service'), [('state', '=', 'in_service')])

    def action_in_transit(self):
        return self._open_assets(_('In Transit'), [('state', '=', 'in_transit')])

    def action_decommissioned(self):
        return self._open_assets(_('Decommissioned'), [('state', '=', 'decommissioned')])

    def action_physical(self):
        return self._open_assets(_('Physical'), [('nature', '=', 'physical')])

    def action_digital(self):
        return self._open_assets(_('Digital'), [('nature', '=', 'digital')])

    def action_logical(self):
        return self._open_assets(_('Logical'), [('nature', '=', 'logical')])

    def action_expiring(self):
        return self._open_assets(_('Licenses expiring within 30 days'), self._expiring_domain())

    def action_expired(self):
        return self._open_assets(_('Expired licenses'), self._expired_domain())
