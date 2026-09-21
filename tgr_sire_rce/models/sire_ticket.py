"""Extension minima de ``sire.ticket`` (tgr_sire_mixin) para vincularlo con
``sire.rce.periodo``.

``sire.ticket`` es deliberadamente generico (ver
``tgr_sire_mixin/models/sire_ticket.py``): no conoce RCE ni ningun otro
libro concreto. Este modulo NO duplica su maquina de estados
(``action_poll``, ``action_download_result``) -- solo agrega el enlace
inverso que necesita el smart button "Tickets" del form de periodo. Mismo
patron que ``tgr_sire_rvie/models/sire_ticket.py``.
"""

from odoo import fields, models


class SireTicket(models.Model):
    _inherit = "sire.ticket"

    rce_periodo_id = fields.Many2one(
        "sire.rce.periodo",
        string="Periodo RCE",
        index=True,
    )
