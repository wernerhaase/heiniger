/** @odoo-module **/
import { ProductLabelSectionAndNoteField, productLabelSectionAndNoteField } from "@account/components/product_label_section_and_note_field/product_label_section_and_note_field";
import { HtmlField } from "@html_editor/fields/html_field";
import { registry } from "@web/core/registry";

export class InvoiceDescription extends ProductLabelSectionAndNoteField {
    static template = "sale_order_html_description.InvoiceDescription";
    static components = { ...ProductLabelSectionAndNoteField.components, HtmlField };
}
registry.category("fields").add("hgr_invoice_description", {
    ...productLabelSectionAndNoteField,
    component: InvoiceDescription,
});
