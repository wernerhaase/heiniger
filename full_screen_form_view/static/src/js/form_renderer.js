/** @odoo-module **/


const { onMounted } = owl;
var localStorage = require('web.local_storage');

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";
patch(FormRenderer.prototype, "full_screen_form_view", {
    setup() {
        this._super();
        if (localStorage.getItem("full_screen") === 'true') {
            this.hideChatter = true;
        }
        else {
            this.hideChatter = false;
        }
        onMounted(() => {
            this._ShowHideRightPanel();
        });
    },
    _onHideRightPanel(ev) {
        ev.preventDefault();
        this.hideChatter = true;
        localStorage.setItem("full_screen", true);
        this._ShowHideRightPanel();
    },

    _onShowRightPanel(ev) {
        ev.preventDefault();
        this.hideChatter = false;
        localStorage.setItem("full_screen", false);
        this._ShowHideRightPanel();
    },

    _ShowHideRightPanel() {
        var $parent = $('span.hide-right-panel').parent();
        if(this.hideChatter) {
            $('span.hide-right-panel').addClass('d-none');
            $('span.show-right-panel').removeClass('d-none');
            if ($('div.o_form_sheet').length) {
                $('div.o_form_sheet').addClass('full-screen-form');
            }
            if ($('div.o_form_view_container').length) {
                $('div.o_form_view_container').next().addClass('d-none');
            }
        }
        else {
            $('span.show-right-panel').addClass('d-none');
            $('span.hide-right-panel').removeClass('d-none');
            if ($('div.o_form_sheet').length) {
                $('div.o_form_sheet').removeClass('full-screen-form');
            }
            if ($('div.o_form_view_container').length) {
                $('div.o_form_view_container').next().removeClass('d-none');
            }
        }
    },
});