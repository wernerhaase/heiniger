/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { AnalyticDistribution } from "@analytic/components/analytic_distribution/analytic_distribution";

// On vendor bill lines, let the user link the cost to a quoted material of the
// project behind the selected analytic account, right inside the analytic
// distribution popup. The choice is optional and stored per analytic row; the
// project profitability report uses it to match each split cost independently
// against the quotation.
const VENDOR_BILL_TYPES = ["in_invoice", "in_refund", "in_receipt"];

patch(AnalyticDistribution.prototype, {
    setup() {
        super.setup(...arguments);
        this.hgrOptionsKey = "";
        this.state.hgrQuotedMaterials = [];
    },

    get hgrQuotedMaterialEnabled() {
        const record = this.props.record;
        if (!("hgr_sale_line_distribution" in record.fields) || this.props.multi_edit) {
            return false;
        }
        const moveType = record.evalContext?.parent?.move_type || record.data.move_type;
        return VENDOR_BILL_TYPES.includes(moveType);
    },

    get hgrShowQuotedMaterial() {
        return this.hgrQuotedMaterialEnabled && this.state.hgrQuotedMaterials.length > 0;
    },

    hgrDistributionKey(line) {
        return line.analyticAccounts
            .reduce((ids, account) => ids.concat(account.accountId || []), [])
            .join(",");
    },

    hgrSelectedQuotedMaterial(line) {
        const mapping = this.props.record.data.hgr_sale_line_distribution || {};
        const key = this.hgrDistributionKey(line);
        if (Object.keys(mapping).length) {
            return Number(mapping[key]) || false;
        }
        return this.props.record.data.hgr_sale_line_id?.id || false;
    },

    hgrLineAccountIds(line) {
        return line.analyticAccounts.map((account) => account.accountId).filter(Boolean);
    },

    hgrQuotedMaterialsForLine(line) {
        const accountIds = this.hgrLineAccountIds(line);
        return this.state.hgrQuotedMaterials.filter((option) =>
            accountIds.includes(option.account_id)
        );
    },

    async hgrLoadQuotedMaterials() {
        if (!this.hgrQuotedMaterialEnabled) {
            return;
        }
        const accountIds = [
            ...new Set(this.state.formattedData.flatMap((line) => this.hgrLineAccountIds(line))),
        ].sort((a, b) => a - b);
        const key = accountIds.join(",");
        if (key === this.hgrOptionsKey) {
            return;
        }
        this.hgrOptionsKey = key;
        this.state.hgrQuotedMaterials = accountIds.length
            ? await this.orm.call("account.move.line", "hgr_quoted_material_options", [accountIds])
            : [];
    },

    async hgrSetQuotedMaterial(ev, line) {
        const saleLineId = Number(ev.target.value) || false;
        const key = this.hgrDistributionKey(line);
        const mapping = { ...(this.props.record.data.hgr_sale_line_distribution || {}) };
        if (saleLineId) {
            mapping[key] = saleLineId;
        } else {
            delete mapping[key];
        }
        await this.props.record.update({
            hgr_sale_line_distribution: mapping,
        });
    },

    async save() {
        await super.save(...arguments);
        if (!this.hgrQuotedMaterialEnabled) {
            return;
        }
        // Keep assignments only while their exact analytic row and quoted
        // material option are still valid.
        const mapping = this.props.record.data.hgr_sale_line_distribution || {};
        const validMapping = {};
        for (const line of this.state.formattedData) {
            const key = this.hgrDistributionKey(line);
            const selected = Number(mapping[key]) || false;
            if (
                selected &&
                this.hgrQuotedMaterialsForLine(line).some((option) => option.id === selected)
            ) {
                validMapping[key] = selected;
            }
        }
        if (JSON.stringify(validMapping) !== JSON.stringify(mapping)) {
            await this.props.record.update({ hgr_sale_line_distribution: validMapping });
        }
    },

    async jsonToData() {
        await super.jsonToData(...arguments);
        await this.hgrLoadQuotedMaterials();
    },

    async lineChanged() {
        const result = await super.lineChanged(...arguments);
        await this.hgrLoadQuotedMaterials();
        return result;
    },

    deleteLine() {
        const result = super.deleteLine(...arguments);
        this.hgrLoadQuotedMaterials();
        return result;
    },
});
