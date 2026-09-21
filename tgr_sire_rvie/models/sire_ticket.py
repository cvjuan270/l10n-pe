"""Extension minima de ``sire.ticket`` (tgr_sire_mixin) para vincularlo con
``sire.rvie.periodo``.

``sire.ticket`` es deliberadamente generico (ver
``tgr_sire_mixin/models/sire_ticket.py``): no conoce RVIE ni ningun otro
libro concreto, y ya trae ``company_id``/``periodo_tributario`` propios. Este
modulo NO duplica su maquina de estados (``action_poll``,
``action_download_result``) -- solo agrega el enlace inverso que necesita el
smart button "Tickets" del form de periodo.
"""

from odoo import fields, models


class SireTicket(models.Model):
    _inherit = "sire.ticket"

    rvie_periodo_id = fields.Many2one(
        "sire.rvie.periodo",
        string="Periodo RVIE",
        index=True,
    )
