/** @odoo-module **/

import { Chatter } from "@mail/chatter/web_portal/chatter";
import "@mail/chatter/web/chatter_patch";
import { fields } from "@mail/core/common/record";
import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    setup() {
        super.setup();
        this.hgrQuotationAttachmentOrder = fields.Attr([]);
        this.hgrQuotationReportAttachments = fields.Attr([]);
    },
});

patch(Chatter.prototype, {
    get attachments() {
        const attachments = super.attachments;
        const thread = this.state.thread;
        if (thread?.model !== "sale.order") {
            return attachments;
        }
        const positions = new Map(
            (thread.hgrQuotationAttachmentOrder || []).map((id, index) => [id, index])
        );
        const reports = new Set(thread.hgrQuotationReportAttachments || []);
        // Linked files first, direct uploads next, generated reports last.
        // A newly uploaded file without a server position also precedes reports.
        const rank = (attachment) => positions.has(attachment.id) ? 0 :
            reports.has(attachment.id) ? 2 : 1;
        return [...attachments].sort((a, b) =>
            rank(a) - rank(b) ||
            (positions.get(a.id) ?? Number.MAX_SAFE_INTEGER) -
            (positions.get(b.id) ?? Number.MAX_SAFE_INTEGER)
        );
    },
});
