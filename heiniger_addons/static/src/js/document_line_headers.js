import { onMounted, onPatched, onWillUnmount, useRef } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";


patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        this.hgrDocumentFormRoot = useRef("compiled_view_root");
        this.hgrObservedStatusBar = null;
        this.hgrStatusBarObserver = new ResizeObserver(() => {
            this.hgrUpdateDocumentLineHeaderOffset();
        });

        onMounted(() => this.hgrRefreshDocumentLineHeaderOffset());
        onPatched(() => this.hgrRefreshDocumentLineHeaderOffset());
        onWillUnmount(() => this.hgrStatusBarObserver.disconnect());
    },

    hgrRefreshDocumentLineHeaderOffset() {
        const root = this.hgrDocumentFormRoot.el;
        const statusBar = root?.querySelector(".o_form_statusbar");
        if (statusBar !== this.hgrObservedStatusBar) {
            this.hgrStatusBarObserver.disconnect();
            this.hgrObservedStatusBar = statusBar;
            if (statusBar) {
                this.hgrStatusBarObserver.observe(statusBar);
            }
        }
        this.hgrUpdateDocumentLineHeaderOffset();
    },

    hgrUpdateDocumentLineHeaderOffset() {
        const root = this.hgrDocumentFormRoot.el;
        const statusBar = this.hgrObservedStatusBar;
        if (!root || !statusBar) {
            return;
        }
        const offset = Math.ceil(statusBar.getBoundingClientRect().height);
        for (const lineTable of root.querySelectorAll(".hgr_document_line_table")) {
            lineTable.style.setProperty("--hgr-document-header-offset", `${offset}px`);
        }
    },
});
