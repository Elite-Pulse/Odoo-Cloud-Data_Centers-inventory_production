# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CloudInvConfigMixin(models.AbstractModel):
    """Base for every configurable list (Settings > Variables)."""
    _name = 'cloud.inv.config.mixin'
    _description = 'Cloud Inventory configurable list'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            dup = self.with_context(active_test=False).search_count(
                [('name', '=ilike', rec.name), ('id', '!=', rec.id)])
            if dup:
                raise ValidationError(_('"%s" already exists in this list.') % rec.name)


class CloudInvBrand(models.Model):
    _name = 'cloud.inv.brand'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'Brand'
    name = fields.Char(string='Brand', required=True)


class CloudInvModel(models.Model):
    _name = 'cloud.inv.model'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'Model'
    name = fields.Char(string='Model', required=True)
    brand_id = fields.Many2one('cloud.inv.brand', string='Brand')

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            dup = self.with_context(active_test=False).search_count(
                [('name', '=ilike', rec.name), ('brand_id', '=', rec.brand_id.id), ('id', '!=', rec.id)])
            if dup:
                raise ValidationError(_('Model "%s" already exists for this brand.') % rec.name)


class CloudInvCpu(models.Model):
    _name = 'cloud.inv.cpu'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'CPU'
    name = fields.Char(string='CPU', required=True)


class CloudInvRam(models.Model):
    _name = 'cloud.inv.ram'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'RAM'
    name = fields.Char(string='RAM', required=True)


class CloudInvStorage(models.Model):
    _name = 'cloud.inv.storage'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'Storage'
    name = fields.Char(string='Storage', required=True)


class CloudInvNic(models.Model):
    _name = 'cloud.inv.nic'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'NIC (network card)'
    name = fields.Char(string='NIC', required=True)


class CloudInvHba(models.Model):
    _name = 'cloud.inv.hba'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'HBA (host bus adapter)'
    name = fields.Char(string='HBA', required=True)


class CloudInvCluster(models.Model):
    _name = 'cloud.inv.cluster'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'Cluster'
    name = fields.Char(string='Cluster', required=True)


class CloudInvSite(models.Model):
    _name = 'cloud.inv.site'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'Site'
    name = fields.Char(string='Site', required=True)


class CloudInvTag(models.Model):
    _name = 'cloud.inv.tag'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'TAG (platform)'
    name = fields.Char(string='TAG', required=True)


class CloudInvProductType(models.Model):
    _name = 'cloud.inv.product.type'
    _inherit = 'cloud.inv.config.mixin'
    _description = 'Product Type'
    name = fields.Char(string='Product Type', required=True)
    nature = fields.Selection([
        ('physical', 'Physical'), ('digital', 'Digital'), ('logical', 'Logical')],
        string='Default Nature', default='physical')
