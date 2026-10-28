/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { InvoiceExtractFormRenderer } from "@account_invoice_extract/js/invoice_extract_form";

// Invoice Extract treats every field nested inside another field widget as an
// x2many line. The analytic distribution popup also nests temporary fields,
// but its parent value is JSON and therefore has no relational record config.
// Ignore those synthetic popup fields while retaining OCR box handling for
// genuine invoice-line fields.
patch(InvoiceExtractFormRenderer.prototype, {
    getBoxType(fullFieldName) {
        if (fullFieldName?.includes(".")) {
            const [parentField] = fullFieldName.split(".");
            const parentValue = this.props.record.data[parentField];
            if (parentValue && !parentValue._config?.fields) {
                return false;
            }
        }
        return super.getBoxType(fullFieldName);
    },
});
