/** @odoo-module **/

import {
    createElement,
} from "@web/core/utils/xml";

import { patch } from "@web/core/utils/patch";
import { FormCompiler } from "@web/views/form/form_compiler";

patch(FormCompiler.prototype, 'full_screen_form_view', {
    compileSheet(el, params) {
        const res = this._super(el, params);

        const $hide_span = createElement('span');
        $hide_span.className = "hide-right-panel";
        $hide_span.setAttribute("t-on-click", '_onHideRightPanel');
        $hide_span.setAttribute("title", 'Hide Chatter');

        const $show_span = createElement('span');
        $show_span.className = "show-right-panel d-none";
        $show_span.setAttribute("t-on-click", '_onShowRightPanel');
        $show_span.setAttribute("title", 'Show Chatter');

        $(res).prepend($hide_span);
        $(res).prepend($show_span);

        return res;
    },
});

