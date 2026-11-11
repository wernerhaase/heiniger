/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { roundDecimals } from "@web/core/utils/numbers";
import { AnalyticDistribution } from "@analytic/components/analytic_distribution/analytic_distribution";

// On vendor bill lines, let the user link the cost to a quoted material of the
// project behind the selected analytic account, right inside the analytic
// distribution popup. The choice is optional and stored per popup row.
//
// Odoo stores ``analytic_distribution`` as {account ids: percentage}, so two
// rows on the same analytic account (e.g. 36.75 % + 63.25 % of one bill line
// on project 725, each for a different quoted material) are merged into one
// 100 % key. The real row split is therefore kept in
// ``hgr_sale_line_distribution`` as {rows: [{key, percentage, sale_line_id}]}
// and expanded back into separate rows whenever the popup is rebuilt. The
// project profitability report uses those rows to split the cost.
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

    // Order-independent form of a distribution key, for comparisons.
    hgrNormalizedKey(key) {
        return String(key || "")
            .split(",")
            .filter(Boolean)
            .map(Number)
            .sort((a, b) => a - b)
            .join(",");
    },

    hgrSelectedQuotedMaterial(line) {
        return line.hgrSaleLineId || false;
    },

    hgrLineAccountIds(line) {
        return line.analyticAccounts.map((account) => account.accountId).filter(Boolean);
    },

    hgrAccountIdsKey() {
        return [
            ...new Set(this.state.formattedData.flatMap((line) => this.hgrLineAccountIds(line))),
        ]
            .sort((a, b) => a - b)
            .join(",");
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
        const key = this.hgrAccountIdsKey();
        if (key === this.hgrOptionsKey) {
            return;
        }
        this.hgrOptionsKey = key;
        this.state.hgrQuotedMaterials = key
            ? await this.orm.call("account.move.line", "hgr_quoted_material_options", [
                  key.split(",").map(Number),
              ])
            : [];
    },

    hgrSetQuotedMaterial(ev, line) {
        // Only this row changes; the record is updated when the popup saves.
        line.hgrSaleLineId = Number(ev.target.value) || false;
    },

    // Rebuild the popup rows from the stored per-row quoted materials.
    hgrApplyStoredRows() {
        const data = this.props.record.data;
        const stored = data.hgr_sale_line_distribution || {};
        const rows = Array.isArray(stored.rows) ? stored.rows : null;
        const result = [];
        for (const line of this.state.formattedData) {
            const key = this.hgrNormalizedKey(this.hgrDistributionKey(line));
            if (!rows) {
                // Legacy data: one quoted material per analytic key, or the
                // original line-wide field.
                const mappingKey = Object.keys(stored).find(
                    (candidate) => this.hgrNormalizedKey(candidate) === key
                );
                line.hgrSaleLineId = mappingKey
                    ? Number(stored[mappingKey]) || false
                    : (!Object.keys(stored).length && data.hgr_sale_line_id?.id) || false;
                result.push(line);
                continue;
            }
            const matching = rows.filter(
                (row) => this.hgrNormalizedKey(row.key) === key && Number(row.percentage) > 0
            );
            const total = matching.reduce((sum, row) => sum + Number(row.percentage), 0);
            if (!matching.length || !total) {
                line.hgrSaleLineId = false;
                result.push(line);
                continue;
            }
            for (const row of matching) {
                result.push({
                    ...line,
                    id: this.nextId++,
                    analyticAccounts: line.analyticAccounts.map((account) => ({ ...account })),
                    percentage: roundDecimals(
                        (line.percentage * Number(row.percentage)) / total,
                        this.decimalPrecision.digits[1] + 2
                    ),
                    hgrSaleLineId: Number(row.sale_line_id) || false,
                });
            }
        }
        this.state.formattedData = result;
    },

    hgrRowsToJson() {
        const lines = this.state.formattedData.filter((line) => this.accountCount(line));
        // Only drop a selection when the options for the current accounts
        // are loaded and the option is really not available any more.
        const optionsLoaded = this.hgrOptionsKey === this.hgrAccountIdsKey();
        const rows = lines.map((line) => {
            let saleLineId = Number(line.hgrSaleLineId) || false;
            if (
                saleLineId &&
                optionsLoaded &&
                !this.hgrQuotedMaterialsForLine(line).some((option) => option.id === saleLineId)
            ) {
                saleLineId = false;
            }
            return {
                key: this.hgrDistributionKey(line),
                percentage: roundDecimals(line.percentage * 100, this.decimalPrecision.digits[1]),
                sale_line_id: saleLineId,
            };
        });
        const keys = rows.map((row) => this.hgrNormalizedKey(row.key));
        const hasRepeatedKey = new Set(keys).size !== keys.length;
        if (!hasRepeatedKey && !rows.some((row) => row.sale_line_id)) {
            return false;
        }
        return { rows };
    },

    async save() {
        if (!this.hgrQuotedMaterialEnabled) {
            return super.save(...arguments);
        }
        // Write the per-row data first: saving the analytic distribution
        // rebuilds the popup rows from it.
        const record = this.props.record;
        const rows = this.hgrRowsToJson();
        const changes = {};
        if (JSON.stringify(rows) !== JSON.stringify(record.data.hgr_sale_line_distribution || false)) {
            changes.hgr_sale_line_distribution = rows;
        }
        if ("hgr_sale_line_id" in record.fields && record.data.hgr_sale_line_id) {
            // The line-wide legacy value is replaced by the per-row data.
            changes.hgr_sale_line_id = false;
        }
        if (Object.keys(changes).length) {
            await record.update(changes);
        }
        return super.save(...arguments);
    },

    async jsonToData() {
        await super.jsonToData(...arguments);
        if (this.hgrQuotedMaterialEnabled) {
            this.hgrApplyStoredRows();
            await this.hgrLoadQuotedMaterials();
        }
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
