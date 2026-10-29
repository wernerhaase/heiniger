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
        if (!fullFieldName) {
            return false;
        }
        const record = this.props.record;
        if (fullFieldName.includes(".")) {
            const [parentField, fieldName] = fullFieldName.split(".");
            const parentRecord = record?.data?.[parentField];
            if (!parentRecord?._config?.fields?.[fieldName]) {
                return false;
            }
        } else if (!record?.fields?.[fullFieldName]) {
            return false;
        }
        return super.getBoxType(fullFieldName);
    },
});
