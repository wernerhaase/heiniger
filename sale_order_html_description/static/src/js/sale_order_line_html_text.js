/** @odoo-module **/

import {
    listSaleOrderLineText,
    ListSaleOrderLineText,
    SaleOrderLineText,
    saleOrderLineText,
} from "@sale/js/sale_order_line_field/sale_order_line_field";
import { SaleOrderLineProductField } from "@sale/js/sale_product_field";
import { HtmlField } from "@html_editor/fields/html_field";
import { markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

export class SaleOrderLineHtmlText extends SaleOrderLineText {
    static template = "sale_order_html_description.SaleOrderLineHtmlText";

    get componentToUse() {
        return HtmlField;
    }

    get displayHtml() {
        return this.props.readonly;
    }

    get htmlValue() {
        return markup(this.props.record.data[this.props.name] || "");
    }
}

export class ListSaleOrderLineHtmlText extends ListSaleOrderLineText {
    static template = "sale_order_html_description.SaleOrderLineHtmlText";

    get displayHtml() {
        return true;
    }

    get htmlValue() {
        return markup(this.props.record.data[this.props.name] || "");
    }
}

export const saleOrderLineHtmlText = {
    ...saleOrderLineText,
    component: SaleOrderLineHtmlText,
};

export const listSaleOrderLineHtmlText = {
    ...listSaleOrderLineText,
    component: ListSaleOrderLineHtmlText,
};

registry.category("fields").add("hgr_sol_html_text", saleOrderLineHtmlText);
registry.category("fields").add("list.hgr_sol_html_text", listSaleOrderLineHtmlText);

patch(SaleOrderLineProductField.prototype, {
    get hgrHtmlLabel() {
        return markup(this.label || "");
    },
});
