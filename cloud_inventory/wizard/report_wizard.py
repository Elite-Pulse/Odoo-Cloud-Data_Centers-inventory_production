# -*- coding: utf-8 -*-
import base64
import io
import re
from collections import Counter
from datetime import datetime

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.osv import expression

from ..models.constants import REASONS, STATES

MANAGER_GROUP = 'cloud_inventory.group_cloud_inv_manager'

# Every field a free-text / audit search looks into.
SEARCH_FIELDS = [
    'name', 'reference', 'service_tag', 'comment', 'ru_display', 'license_key',
    'brand_id.name', 'model_id.name', 'cluster_id.name', 'cpu_id.name', 'ram_id.name',
    'storage_id.name', 'tag_id.name', 'site_id.name', 'product_type_id.name',
    'datacenter_id.name', 'datacenter_id.code', 'hall_id.name', 'room_id.name',
    'rack_id.name', 'rack_id.complete_name', 'responsible_id.name',
    'nic_ids.name', 'hba_ids.name', 'warehouse_id.name', 'shelf', 'destination_id.name',
    'request_ref', 'rack_lane',
]

# (key, asset field) -> columns of the Excel export
XLSX_COLUMNS = [
    ('reference', 'reference'), ('nature', 'nature'), ('product_type', 'product_type_id'),
    ('brand', 'brand_id'), ('model', 'model_id'), ('name', 'name'), ('cluster', 'cluster_id'),
    ('cpu', 'cpu_id'), ('ram', 'ram_id'), ('storage', 'storage_id'), ('nic', 'nic_ids'), ('hba', 'hba_ids'), ('service_tag', 'service_tag'),
    ('tag', 'tag_id'), ('datacenter', 'datacenter_id'), ('warehouse', 'warehouse_id'), ('hall', 'hall_id'), ('room', 'room_id'),
    ('lane', 'rack_lane'), ('rack', 'rack_id'), ('ru', 'ru_display'), ('site', 'site_id'), ('date_in', 'date_in'),
    ('date_out', 'date_out'), ('state', 'state'), ('last_reason', 'last_reason'), ('destination', 'destination_id'),
    ('request_ref', 'request_ref'), ('responsible', 'responsible_id'),
    ('license_expiry', 'license_expiry'), ('comment', 'comment'),
]

# Narrower column set for the landscape PDF
PDF_COLUMNS = [
    ('reference', 'reference'), ('product_type', 'product_type_id'), ('brand', 'brand_id'),
    ('model', 'model_id'), ('name', 'name'), ('cluster', 'cluster_id'), ('cpu', 'cpu_id'),
    ('ram', 'ram_id'), ('storage', 'storage_id'), ('nic', 'nic_ids'), ('hba', 'hba_ids'),
    ('service_tag', 'service_tag'),
    ('tag', 'tag_id'), ('state', 'state'), ('location', None), ('ru', 'ru_display'), ('site', 'site_id'),
    ('date_in', 'date_in'), ('date_out', 'date_out'), ('responsible', 'responsible_id'),
]


class CloudInvReportWizard(models.TransientModel):
    _name = 'cloud.inv.report.wizard'
    _description = 'Cloud Inventory Export (Excel / PDF)'

    # Selection coming from a list view (optional)
    asset_ids = fields.Many2many('cloud.inv.asset', 'cloud_inv_rw_asset_rel', 'wiz_id', 'asset_id',
                                 string='Selection')

    report_type = fields.Selection([
        ('detailed', 'Detailed report (all columns)'),
        ('summary', 'Summary report (counts only)'),
        ('audit', 'Audit report (search coverage and matches)'),
    ], string='Report Type', default='detailed', required=True)

    # Audit search
    search_terms = fields.Text(
        string='Search Terms',
        help='One or several terms, one per line (or separated by commas / semicolons). '
             'Each term is searched in every field: name, reference, service tag, brand, model, '
             'cluster, CPU, RAM, storage, TAG, site, location, responsible, comment, license key, dates...')
    exact_match = fields.Boolean(string='Exact Match',
                                 help='The whole value must be equal to the term instead of just containing it.')
    match_mode = fields.Selection([
        ('any', 'Any term (OR)'), ('all', 'All terms (AND)')],
        string='Match Mode', default='any', required=True)

    # Filters
    datacenter_ids = fields.Many2many('cloud.inv.datacenter', 'cloud_inv_rw_dc_rel', 'wiz_id', 'rec_id', string='Datacenters')
    hall_ids = fields.Many2many('cloud.inv.hall', 'cloud_inv_rw_hall_rel', 'wiz_id', 'rec_id', string='Halls')
    room_ids = fields.Many2many('cloud.inv.room', 'cloud_inv_rw_room_rel', 'wiz_id', 'rec_id', string='Rooms')
    rack_ids = fields.Many2many('cloud.inv.rack', 'cloud_inv_rw_rack_rel', 'wiz_id', 'rec_id', string='Racks')
    product_type_ids = fields.Many2many('cloud.inv.product.type', 'cloud_inv_rw_type_rel', 'wiz_id', 'rec_id', string='Product Types')
    brand_ids = fields.Many2many('cloud.inv.brand', 'cloud_inv_rw_brand_rel', 'wiz_id', 'rec_id', string='Brands')
    model_ids = fields.Many2many('cloud.inv.model', 'cloud_inv_rw_model_rel', 'wiz_id', 'rec_id', string='Models')
    cluster_ids = fields.Many2many('cloud.inv.cluster', 'cloud_inv_rw_cluster_rel', 'wiz_id', 'rec_id', string='Clusters')
    cpu_ids = fields.Many2many('cloud.inv.cpu', 'cloud_inv_rw_cpu_rel', 'wiz_id', 'rec_id', string='CPU')
    ram_ids = fields.Many2many('cloud.inv.ram', 'cloud_inv_rw_ram_rel', 'wiz_id', 'rec_id', string='RAM')
    storage_ids = fields.Many2many('cloud.inv.storage', 'cloud_inv_rw_storage_rel', 'wiz_id', 'rec_id', string='Storage')
    tag_ids = fields.Many2many('cloud.inv.tag', 'cloud_inv_rw_tag_rel', 'wiz_id', 'rec_id', string='TAG')
    site_ids = fields.Many2many('cloud.inv.site', 'cloud_inv_rw_site_rel', 'wiz_id', 'rec_id', string='Sites')
    responsible_ids = fields.Many2many('res.users', 'cloud_inv_rw_user_rel', 'wiz_id', 'user_id', string='Responsibles')
    nature = fields.Selection([('physical', 'Physical'), ('digital', 'Digital'), ('logical', 'Logical')],
                              string='Nature')
    state = fields.Selection(STATES, string='Status')
    warehouse_ids = fields.Many2many('cloud.inv.warehouse', 'cloud_inv_rw_wh_rel', 'wiz_id', 'rec_id', string='Warehouses')
    nic_ids = fields.Many2many('cloud.inv.nic', 'cloud_inv_rw_nic_rel', 'wiz_id', 'rec_id', string='NIC')
    hba_ids = fields.Many2many('cloud.inv.hba', 'cloud_inv_rw_hba_rel', 'wiz_id', 'rec_id', string='HBA')
    reason = fields.Selection(REASONS, string='Last Reason')
    lane = fields.Selection([('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')], string='Lane')
    include_history = fields.Boolean(string='Include movement history',
                                     help='Adds a sheet with every movement of the selected items.')
    date_in_from = fields.Date(string='Entered From')
    date_in_to = fields.Date(string='Entered To')
    date_out_from = fields.Date(string='Exited From')
    date_out_to = fields.Date(string='Exited To')

    file_data = fields.Binary(string='File', readonly=True)
    file_name = fields.Char(string='File Name')

    # ------------------------------------------------------------------
    # access
    # ------------------------------------------------------------------
    def _check_manager(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_('Only Cloud Inventory managers and administrators can export data.'))

    # ------------------------------------------------------------------
    # search terms
    # ------------------------------------------------------------------
    def _get_terms(self):
        self.ensure_one()
        seen, terms = set(), []
        for part in re.split(r'[\n\r;,]+', self.search_terms or ''):
            part = part.strip()
            if part and part.lower() not in seen:
                seen.add(part.lower())
                terms.append(part)
        return terms

    def _term_leaves(self, term):
        """Domain matching `term` in any field of an asset."""
        self.ensure_one()
        exact = self.exact_match
        if exact:
            op = '=ilike'
            val = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        else:
            op, val = 'ilike', term
        leaves = [(f, op, val) for f in SEARCH_FIELDS]
        low = term.lower()
        fg = self.env['cloud.inv.asset'].fields_get(['nature', 'state', 'last_reason'])
        for fname in ('nature', 'state', 'last_reason'):
            for key, label in fg[fname]['selection']:
                hit = (low in (key.lower(), label.lower())) if exact else (low in label.lower() or low == key.lower())
                if hit:
                    leaves.append((fname, '=', key))
        for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
            try:
                day = datetime.strptime(term, fmt).date()
            except ValueError:
                continue
            for dfield in ('date_in', 'date_out', 'license_expiry'):
                leaves.append((dfield, '=', day))
            break
        if term.isdigit():
            leaves.append(('license_seats', '=', int(term)))
        return expression.OR([[leaf] for leaf in leaves])

    @staticmethod
    def _term_in(term, text, exact):
        t, v = term.lower(), (text or '').lower()
        return v == t if exact else t in v

    def _asset_values(self, a, fg):
        """(field label, text) pairs used to tell WHERE a term was found."""
        sel = {f: dict(fg[f]['selection']) for f in ('nature', 'state', 'last_reason')}

        def L(f):
            return fg[f]['string']
        vals = [
            (L('name'), a.name), (L('reference'), a.reference), (L('service_tag'), a.service_tag),
            (L('comment'), a.comment), (L('ru_display'), a.ru_display), (L('license_key'), a.license_key),
            (L('brand_id'), a.brand_id.name), (L('model_id'), a.model_id.name),
            (L('cluster_id'), a.cluster_id.name), (L('cpu_id'), a.cpu_id.name),
            (L('ram_id'), a.ram_id.name), (L('storage_id'), a.storage_id.name),
            (L('nic_ids'), ', '.join(a.nic_ids.mapped('name'))), (L('hba_ids'), ', '.join(a.hba_ids.mapped('name'))),
            (L('warehouse_id'), a.warehouse_id.name), (L('shelf'), a.shelf), (L('destination_id'), a.destination_id.name),
            (L('request_ref'), a.request_ref), (L('rack_lane'), a.rack_lane),
            (L('last_reason'), sel['last_reason'].get(a.last_reason)),
            (L('tag_id'), a.tag_id.name), (L('site_id'), a.site_id.name),
            (L('product_type_id'), a.product_type_id.name),
            (L('datacenter_id'), a.datacenter_id.name), (L('datacenter_id'), a.datacenter_id.code),
            (L('hall_id'), a.hall_id.name), (L('room_id'), a.room_id.name),
            (L('rack_id'), a.rack_id.name), (L('rack_id'), a.rack_id.complete_name),
            (L('responsible_id'), a.responsible_id.name),
            (L('nature'), sel['nature'].get(a.nature)), (L('state'), sel['state'].get(a.state)),
        ]
        for f in ('date_in', 'date_out', 'license_expiry'):
            d = a[f]
            if d:
                vals.append((L(f), d.strftime('%Y-%m-%d')))
                vals.append((L(f), d.strftime('%d/%m/%Y')))
        return [(label, str(v)) for label, v in vals if v]

    # ------------------------------------------------------------------
    # selection of assets
    # ------------------------------------------------------------------
    def _get_domain(self, with_terms=True):
        self.ensure_one()
        if self.asset_ids:
            return [('id', 'in', self.asset_ids.ids)]
        d = []
        m2m = [
            ('datacenter_ids', 'datacenter_id'), ('hall_ids', 'hall_id'), ('room_ids', 'room_id'),
            ('rack_ids', 'rack_id'), ('product_type_ids', 'product_type_id'), ('brand_ids', 'brand_id'),
            ('model_ids', 'model_id'), ('cluster_ids', 'cluster_id'), ('cpu_ids', 'cpu_id'),
            ('ram_ids', 'ram_id'), ('storage_ids', 'storage_id'), ('tag_ids', 'tag_id'),
            ('site_ids', 'site_id'), ('responsible_ids', 'responsible_id'),
            ('warehouse_ids', 'warehouse_id'),
        ]
        for wf, af in m2m:
            if self[wf]:
                d.append((af, 'in', self[wf].ids))
        if self.nic_ids:
            d.append(('nic_ids', 'in', self.nic_ids.ids))
        if self.hba_ids:
            d.append(('hba_ids', 'in', self.hba_ids.ids))
        if self.reason:
            d.append(('last_reason', '=', self.reason))
        if self.lane:
            d.append(('rack_lane', '=', self.lane))
        if self.nature:
            d.append(('nature', '=', self.nature))
        if self.state:
            d.append(('state', '=', self.state))
        if self.date_in_from:
            d.append(('date_in', '>=', self.date_in_from))
        if self.date_in_to:
            d.append(('date_in', '<=', self.date_in_to))
        if self.date_out_from:
            d.append(('date_out', '>=', self.date_out_from))
        if self.date_out_to:
            d.append(('date_out', '<=', self.date_out_to))
        terms = self._get_terms()
        if with_terms and terms:
            clauses = [self._term_leaves(t) for t in terms]
            joined = expression.OR(clauses) if self.match_mode == 'any' else expression.AND(clauses)
            d = expression.AND([d, joined])
        return d

    def get_assets(self):
        self.ensure_one()
        return self.env['cloud.inv.asset'].search(
            self._get_domain(), order='datacenter_id, rack_id, ru_start, name')

    def get_filters_summary(self):
        self.ensure_one()
        if self.asset_ids:
            return _('Manual selection of %s item(s)') % len(self.asset_ids)
        fnames = ['datacenter_ids', 'hall_ids', 'room_ids', 'rack_ids', 'product_type_ids', 'brand_ids',
                  'model_ids', 'cluster_ids', 'cpu_ids', 'ram_ids', 'storage_ids', 'tag_ids',
                  'site_ids', 'responsible_ids', 'warehouse_ids', 'nic_ids', 'hba_ids']
        fg = self.fields_get(fnames + ['nature', 'state', 'reason', 'lane'])
        parts = []
        terms = self._get_terms()
        if terms:
            parts.append(_('Search terms: %s') % ', '.join(terms))
            parts.append(_('Exact match') if self.exact_match else _('Partial match'))
            parts.append(_('All terms must match') if self.match_mode == 'all' else _('Any term may match'))
        for f in fnames:
            if self[f]:
                parts.append('%s: %s' % (fg[f]['string'], ', '.join(self[f].mapped('display_name'))))
        if self.nature:
            parts.append('%s: %s' % (fg['nature']['string'], dict(fg['nature']['selection'])[self.nature]))
        if self.reason:
            parts.append('%s: %s' % (fg['reason']['string'], dict(fg['reason']['selection'])[self.reason]))
        if self.lane:
            parts.append('%s: %s' % (fg['lane']['string'], self.lane))
        if self.state:
            parts.append('%s: %s' % (fg['state']['string'], dict(fg['state']['selection'])[self.state]))
        if self.date_in_from or self.date_in_to:
            parts.append(_('Entry date: %(a)s to %(b)s') % {
                'a': self.date_in_from or '...', 'b': self.date_in_to or '...'})
        if self.date_out_from or self.date_out_to:
            parts.append(_('Exit date: %(a)s to %(b)s') % {
                'a': self.date_out_from or '...', 'b': self.date_out_to or '...'})
        return ' | '.join(parts) or _('No filter (whole inventory)')

    # ------------------------------------------------------------------
    # report data (shared by Excel and PDF)
    # ------------------------------------------------------------------
    def get_report_data(self):
        self.ensure_one()
        self._check_manager()
        Asset = self.env['cloud.inv.asset']
        assets = self.get_assets()
        terms = self._get_terms()
        report_type = self.report_type
        fnames = sorted({f for _k, f in XLSX_COLUMNS + PDF_COLUMNS if f} | {
            'nature', 'state', 'license_key', 'comment', 'ru_display', 'last_reason'})
        fg = Asset.fields_get(fnames)
        sel = {f: dict(fg[f]['selection']) for f in ('nature', 'state', 'last_reason')}
        exact = self.exact_match

        def fmt_date(d):
            return d.strftime('%d/%m/%Y') if d else ''

        def row_dict(a):
            return {
                'reference': a.reference, 'nature': sel['nature'].get(a.nature),
                'product_type': a.product_type_id.name, 'brand': a.brand_id.name,
                'model': a.model_id.name, 'name': a.name, 'cluster': a.cluster_id.name,
                'cpu': a.cpu_id.name, 'ram': a.ram_id.name, 'storage': a.storage_id.name,
                'nic': ', '.join(a.nic_ids.mapped('name')), 'hba': ', '.join(a.hba_ids.mapped('name')),
                'warehouse': a.warehouse_id.display_name, 'lane': a.rack_lane,
                'last_reason': sel['last_reason'].get(a.last_reason), 'destination': a.destination_id.name,
                'request_ref': a.request_ref,
                'service_tag': a.service_tag, 'tag': a.tag_id.name,
                'datacenter': a.datacenter_id.name, 'hall': a.hall_id.name, 'room': a.room_id.name,
                'rack': a.rack_id.name, 'ru': a.ru_display, 'site': a.site_id.name,
                'date_in': fmt_date(a.date_in), 'date_out': fmt_date(a.date_out),
                'state': sel['state'].get(a.state), 'responsible': a.responsible_id.name,
                'license_expiry': fmt_date(a.license_expiry), 'comment': a.comment,
                'location': a.rack_id.complete_name or a.warehouse_id.display_name or a.destination_id.name or ' / '.join(
                    filter(None, [a.datacenter_id.code, a.hall_id.name, a.room_id.name])),
            }

        # --- search coverage (audit) ---
        coverage, matched_terms, matched_in = [], {}, {}
        if terms:
            base = self._get_domain(with_terms=False)
            for term in terms:
                found = Asset.search(expression.AND([base, self._term_leaves(term)]))
                coverage.append({
                    'term': term, 'count': len(found),
                    'refs': ', '.join(found.mapped('reference')[:30]) + (' ...' if len(found) > 30 else ''),
                })
                for a in found:
                    matched_terms.setdefault(a.id, []).append(term)
            if report_type == 'audit':
                for a in assets:
                    labels = []
                    values = self._asset_values(a, fg)
                    for term in matched_terms.get(a.id, []):
                        for label, text in values:
                            if self._term_in(term, text, exact) and label not in labels:
                                labels.append(label)
                    matched_in[a.id] = labels

        # --- columns ---
        xlsx_headers = [fg[f]['string'] for _k, f in XLSX_COLUMNS]
        pdf_headers = [fg[f]['string'] if f else _('Location') for _k, f in PDF_COLUMNS]
        audit_headers = [_('Matched terms'), _('Matched in')] if report_type == 'audit' else []

        xlsx_rows, pdf_rows = [], []
        for a in assets:
            rd = row_dict(a)
            extra = []
            if report_type == 'audit':
                extra = [', '.join(matched_terms.get(a.id, [])), ', '.join(matched_in.get(a.id, []))]
            xlsx_rows.append([rd.get(k) or '' for k, _f in XLSX_COLUMNS] + extra)
            pdf_rows.append({'cells': [rd.get(k) or '' for k, _f in PDF_COLUMNS] + extra,
                             'out': a.state == 'decommissioned'})

        # --- summary tables ---
        def count_by(getter):
            c = Counter((getter(a) or _('Undefined')) for a in assets)
            return sorted(c.items(), key=lambda x: (-x[1], x[0]))

        summary = [
            (fg['nature']['string'], count_by(lambda a: sel['nature'].get(a.nature))),
            (fg['state']['string'], count_by(lambda a: sel['state'].get(a.state))),
            (Asset.fields_get(['datacenter_id'])['datacenter_id']['string'], count_by(lambda a: a.datacenter_id.name)),
            (fg['product_type_id']['string'], count_by(lambda a: a.product_type_id.name)),
            (fg['brand_id']['string'], count_by(lambda a: a.brand_id.name)),
            (fg['cluster_id']['string'], count_by(lambda a: a.cluster_id.name)),
        ]

        history = []
        if self.include_history and assets:
            mfg = self.env['cloud.inv.movement'].fields_get(['move_type', 'reason'])
            mt, rs = dict(mfg['move_type']['selection']), dict(mfg['reason']['selection'])
            for m in self.env['cloud.inv.movement'].search([('asset_id', 'in', assets.ids)], order='asset_id, date'):
                history.append([
                    m.asset_id.reference, m.asset_id.name,
                    fields.Datetime.context_timestamp(self, m.date).strftime('%d/%m/%Y %H:%M'),
                    mt.get(m.move_type), m.from_location, m.to_location, rs.get(m.reason),
                    m.replacement_id.display_name, m.request_ref, m.user_id.name, m.comment])
        history_headers = [_('Reference'), _('Name'), _('Date'), _('Movement Type'), _('From'), _('To'),
                           _('Reason'), _('Replaced By / Replacing'), _('Request / Mail Reference'),
                           _('Done By'), _('Comment')]

        type_label = dict(self.fields_get(['report_type'])['report_type']['selection'])[report_type]
        generated = fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d/%m/%Y %H:%M')
        return {
            'report_type': report_type,
            'title': '%s - %s' % (_('Cloud Inventory'), type_label.split(' (')[0]),
            'filters': self.get_filters_summary(),
            'meta': _('%(count)s item(s) - generated on %(date)s by %(user)s') % {
                'count': len(assets), 'date': generated, 'user': self.env.user.name},
            'count': len(assets),
            'xlsx_headers': xlsx_headers + audit_headers,
            'xlsx_rows': xlsx_rows,
            'pdf_headers': pdf_headers + audit_headers,
            'pdf_rows': pdf_rows,
            'summary': summary,
            'history': history,
            'history_headers': history_headers,
            'coverage': coverage,
            'labels': {
                'coverage': _('Search coverage'), 'term': _('Search term'), 'result': _('Result'),
                'matches': _('Matches'), 'references': _('References'), 'found': _('Found'),
                'not_found': _('Not found'), 'count': _('Count'),
                'no_result': _('No result for these filters.'),
            },
        }

    # ------------------------------------------------------------------
    # exports
    # ------------------------------------------------------------------
    def action_print_pdf(self):
        self.ensure_one()
        self._check_manager()
        if self.report_type != 'audit' and not self.get_assets():
            raise UserError(_('No result for these filters.'))
        return self.env.ref('cloud_inventory.action_report_assets').report_action(self)

    def action_export_xlsx(self):
        self.ensure_one()
        self._check_manager()
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('The Python package xlsxwriter is required.'))
        data = self.get_report_data()
        if not data['count'] and data['report_type'] != 'audit':
            raise UserError(_('No result for these filters.'))
        lb = data['labels']

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        f_title = wb.add_format({'bold': True, 'font_size': 16, 'font_color': '#714B67'})
        f_sub = wb.add_format({'italic': True, 'font_color': '#555555'})
        f_head = wb.add_format({'bold': True, 'bg_color': '#714B67', 'font_color': '#FFFFFF', 'border': 1,
                                'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        f_cell = wb.add_format({'border': 1, 'valign': 'top'})
        f_alt = wb.add_format({'border': 1, 'valign': 'top', 'bg_color': '#F4EFF3'})
        f_bad = wb.add_format({'border': 1, 'valign': 'top', 'bg_color': '#F8D7DA', 'bold': True})
        f_ok = wb.add_format({'border': 1, 'valign': 'top', 'bg_color': '#D4EDDA'})

        def intro(ws):
            ws.write(0, 0, data['title'], f_title)
            ws.write(1, 0, data['meta'], f_sub)
            ws.write(2, 0, data['filters'], f_sub)

        if data['report_type'] != 'summary':
            ws = wb.add_worksheet(_('Inventory'))
            intro(ws)
            hr = 4
            ws.set_row(hr, 30)
            widths = [len(h) + 2 for h in data['xlsx_headers']]
            for c, h in enumerate(data['xlsx_headers']):
                ws.write(hr, c, h, f_head)
            for i, row in enumerate(data['xlsx_rows']):
                fmt = f_alt if i % 2 else f_cell
                for c, v in enumerate(row):
                    ws.write(hr + 1 + i, c, v or '', fmt)
                    widths[c] = max(widths[c], min(len(str(v or '')) + 2, 45))
            for c, w in enumerate(widths):
                ws.set_column(c, c, w)
            if data['xlsx_rows']:
                ws.autofilter(hr, 0, hr + len(data['xlsx_rows']), len(data['xlsx_headers']) - 1)
            ws.freeze_panes(hr + 1, 0)

        if data['history']:
            wsh = wb.add_worksheet(_('Movement history'))
            intro(wsh)
            for c, h in enumerate(data['history_headers']):
                wsh.write(4, c, h, f_head)
                wsh.set_column(c, c, 22)
            for i, row in enumerate(data['history']):
                for c, v in enumerate(row):
                    wsh.write(5 + i, c, v or '', f_alt if i % 2 else f_cell)
            wsh.autofilter(4, 0, 4 + len(data['history']), len(data['history_headers']) - 1)
            wsh.freeze_panes(5, 0)

        ws2 = wb.add_worksheet(_('Summary'))
        intro(ws2)
        ws2.set_column(0, 0, 36)
        ws2.set_column(1, 1, 12)
        r = 4
        for title, rows in data['summary']:
            ws2.write(r, 0, title, f_head)
            ws2.write(r, 1, lb['count'], f_head)
            r += 1
            for label, cnt in rows:
                ws2.write(r, 0, label, f_cell)
                ws2.write(r, 1, cnt, f_cell)
                r += 1
            r += 1

        if data['report_type'] == 'audit':
            ws3 = wb.add_worksheet(_('Search coverage'))
            intro(ws3)
            for c, (h, w) in enumerate([(lb['term'], 34), (lb['result'], 14), (lb['matches'], 10),
                                        (lb['references'], 80)]):
                ws3.write(4, c, h, f_head)
                ws3.set_column(c, c, w)
            for i, cov in enumerate(data['coverage']):
                found = cov['count'] > 0
                ws3.write(5 + i, 0, cov['term'], f_cell)
                ws3.write(5 + i, 1, lb['found'] if found else lb['not_found'], f_ok if found else f_bad)
                ws3.write(5 + i, 2, cov['count'], f_cell)
                ws3.write(5 + i, 3, cov['refs'], f_cell)
        wb.close()

        self.write({
            'file_data': base64.b64encode(buf.getvalue()),
            'file_name': 'cloud_inventory_%s_%s.xlsx' % (
                data['report_type'], fields.Date.context_today(self).strftime('%Y%m%d')),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=file_data&filename_field=file_name&download=true' % (
                self._name, self.id),
            'target': 'self',
        }

    def action_reset(self):
        self.ensure_one()
        vals = {f: [(5, 0, 0)] for f, fld in self._fields.items() if fld.type == 'many2many'}
        vals.update({'nature': False, 'state': False, 'date_in_from': False, 'date_in_to': False,
                     'date_out_from': False, 'date_out_to': False, 'search_terms': False,
                     'exact_match': False, 'match_mode': 'any', 'reason': False,
                     'lane': False, 'include_history': False})
        self.write(vals)
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}
