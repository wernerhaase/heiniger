/** @odoo-module **/

import { onMounted, onWillUnmount, useEffect, useRef } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

const FULL_SCREEN_KEY = "full_screen";

patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        this.hideChatter = browser.localStorage.getItem(FULL_SCREEN_KEY) === "true";
        this.fullScreenRootRef = useRef("compiled_view_root");
        this._onFullScreenToggleClick = (ev) => {
            const hideButton = ev.target.closest(".o_full_screen_toggle_hide");
            if (hideButton) {
                ev.preventDefault();
                this._setHideChatter(true);
                return;
            }
            const showButton = ev.target.closest(".o_full_screen_toggle_show");
            if (showButton) {
                ev.preventDefault();
                this._setHideChatter(false);
            }
        };
        onMounted(() => {
            this._applyRightPanelState();
            const root = this.fullScreenRootRef?.el || this.el || document;
            root.addEventListener("click", this._onFullScreenToggleClick);
        });
        onWillUnmount(() => {
            const root = this.fullScreenRootRef?.el || this.el || document;
            root.removeEventListener("click", this._onFullScreenToggleClick);
        });
        useEffect(
            () => {
                this._applyRightPanelState();
            },
            () => [this.props.record?.resId, this.props.record?.resModel]
        );
    },

    _onHideRightPanel(ev) {
        ev.preventDefault();
        this._setHideChatter(true);
    },

    _onShowRightPanel(ev) {
        ev.preventDefault();
        this._setHideChatter(false);
    },

    _setHideChatter(hideChatter) {
        this.hideChatter = hideChatter;
        browser.localStorage.setItem(FULL_SCREEN_KEY, hideChatter ? "true" : "false");
        this._applyRightPanelState();
    },

    _applyRightPanelState() {
        const root = this.fullScreenRootRef?.el || this.el || document;
        const toggleContainer = root.querySelector(".o_full_screen_chatter_toggle");
        const statusbarStatus = root.querySelector(
            ".o_form_statusbar .o_field_statusbar .o_statusbar_status"
        );
        if (toggleContainer && statusbarStatus && toggleContainer.parentElement !== statusbarStatus) {
            statusbarStatus.prepend(toggleContainer);
        }

        const hideButton = root.querySelector(".o_full_screen_toggle_hide");
        const showButton = root.querySelector(".o_full_screen_toggle_show");
        if (hideButton) {
            hideButton.classList.toggle("d-none", this.hideChatter);
        }
        if (showButton) {
            showButton.classList.toggle("d-none", !this.hideChatter);
        }

        const formSheetBg = root.querySelector(".o_form_sheet_bg");
        if (formSheetBg) {
            formSheetBg.classList.toggle("full-screen-form", this.hideChatter);
        }
        const formSheet = root.querySelector(".o_form_sheet");
        if (formSheet) {
            formSheet.classList.toggle("full-screen-form", this.hideChatter);
        }

        const chatterContainers = root.querySelectorAll(".o-mail-Form-chatter");
        for (const chatterContainer of chatterContainers) {
            chatterContainer.classList.toggle("d-none", this.hideChatter);
        }
    },
});
