/** @odoo-module **/
import { useEffect, useState } from '@odoo/owl';
import { FileViewer } from '@web/core/file_viewer/file_viewer';
import { useService } from '@web/core/utils/hooks';
import { patch } from '@web/core/utils/patch';

patch(FileViewer.prototype, {
    setup() {
        super.setup(...arguments);
        this.hgrOrm = useService('orm');
        this.hgrAction = useService('action');
        this.hgrEditor = useState({available: false, busy: false});
        useEffect(() => {
            let cancelled = false;
            this.hgrEditor.available = false;
            const file = this.state.file;
            if (file?.isPdf && Number.isInteger(file.id)) {
                this.hgrOrm.call('ir.attachment', 'hgr_pdf_edit_available', [[file.id]])
                    .then(available => { if (!cancelled) this.hgrEditor.available = available; })
                    .catch(() => {});
            }
            return () => { cancelled = true; };
        }, () => [this.state.file?.id]);
    },
    async hgrEditPdf() {
        if (this.hgrEditor.busy) return;
        this.hgrEditor.busy = true;
        try {
            const action = await this.hgrOrm.call('ir.attachment', 'action_hgr_edit_pdf', [[this.state.file.id]]);
            await this.hgrAction.doAction(action);
            this.close();
        } finally {
            this.hgrEditor.busy = false;
        }
    },
});
