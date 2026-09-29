/** @odoo-module **/

import {
    createElement,
} from "@web/core/utils/xml";

import { patch } from "@web/core/utils/patch";
import { FormCompiler } from "@web/views/form/form_compiler";

patch(FormCompiler.prototype, {
    compile(el, params) {
        const res = super.compile(el, params);

        const hideSpan = createElement("button", {
            class: "btn btn-secondary o_full_screen_toggle o_full_screen_toggle_hide",
            "t-if": "!__comp__.env.inDialog and __comp__.mailStore",
            type: "button",
            title: "Hide Chatter",
        });
        hideSpan.textContent = "Hide Chatter";

        const showSpan = createElement("button", {
            class: "btn btn-secondary o_full_screen_toggle o_full_screen_toggle_show d-none",
            "t-if": "!__comp__.env.inDialog and __comp__.mailStore",
            type: "button",
            title: "Show Chatter",
        });
        showSpan.textContent = "Show Chatter";

        const toggleContainer = createElement("div", {
            class: "o_full_screen_chatter_toggle d-flex align-items-center ms-2",
        });
        toggleContainer.append(showSpan, hideSpan);
        const statusBar = res.querySelector(".o_form_statusbar");
        if (statusBar) {
            statusBar.append(toggleContainer);
        }

        return res;
    },
});
