/** @odoo-module **/
/* Copyright 2026 tagre.pe
 * License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl). */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _lt } from "@web/core/l10n/translation";
import { CharField } from "@web/views/fields/char/char_field";
import { useState } from "@odoo/owl";

export class VatConsultCharField extends CharField {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.consultState = useState({ loading: false });
    }

    get canConsult() {
        // The server validates that the type is DNI or RUC.
        return Boolean(this.props.record.data.l10n_latam_identification_type_id);
    }

    async onConsultClick() {
        // Read the live input value: CharField only commits to the record on
        // change (blur), so props.value may lag behind what the user typed.
        const vatNumber = (this.input.el ? this.input.el.value : this.props.value || "").trim();
        if (!this.canConsult || !vatNumber || this.consultState.loading) {
            return;
        }
        const record = this.props.record;
        const idType = record.data.l10n_latam_identification_type_id;
        this.consultState.loading = true;
        try {
            const result = await this.orm.call("res.partner", "l10n_pe_vat_consult", [
                vatNumber,
                idType[0],
            ]);
            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
                return;
            }
            // With a non-PE company the address sub-form does not inject
            // l10n_pe_district/city_id and record.update() would crash on
            // fields missing from the view.
            const values = {};
            for (const [field, value] of Object.entries(result.values)) {
                if (field in record.activeFields) {
                    values[field] = value;
                }
            }
            // The city_id onchange resets zip from res.city.zipcode (empty
            // for Peru), so the ubigeo must be applied in a second update.
            const zipValue = values.zip;
            delete values.zip;
            await record.update(values);
            if (zipValue) {
                await record.update({ zip: zipValue });
            }
        } finally {
            this.consultState.loading = false;
        }
    }
}

VatConsultCharField.template = "l10n_pe_vat.VatConsultCharField";
VatConsultCharField.displayName = _lt("VAT with DNI/RUC lookup");

registry.category("fields").add("l10n_pe_vat_consult", VatConsultCharField);
