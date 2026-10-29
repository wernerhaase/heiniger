/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formatCurrency } from "@web/core/currency";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { formatFloat } from "@web/views/fields/formatters";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class HgrProjectProfitability extends Component {
    static template = "heiniger_addons.ProjectProfitability";
    static components = { RecordSelector };
    static props = { ...standardActionServiceProps };

    get hgrBreadcrumbs() {
        return this.env.config?.breadcrumbs || [];
    }

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        const context = this.props.action.context || {};
        this.labels = {
            project: _t("Project"),
            employee: _t("Employee"),
            workCategory: _t("Work Category"),
            product: _t("Product"),
            selectProject: _t("All projects"),
            selectEmployee: _t("Select employee..."),
            selectWorkCategory: _t("Select work category..."),
            selectProduct: _t("Select quoted product (optional)..."),
        };
        this.state = useState({
            projectId: context.default_project_id || false,
            saleOrderId: context.default_sale_order_id || false,
            dateFrom: "",
            dateTo: "",
            data: null,
            loading: true,
            activeTab: "summary",
            labourView: "detail",
            manualOpen: false,
            manualOptions: { services: [] },
            manualValidated: false,
            validationToken: false,
            manual: {
                entryType: "labour",
                date: new Date().toISOString().slice(0, 10),
                employeeId: false,
                saleLineId: false,
                isManualService: false,
                manualServiceName: "",
                workCategoryId: false,
                productId: false,
                hours: "",
                amount: "",
                description: "",
            },
        });
        onWillStart(() => this.load());
    }

    get projectDomain() {
        return [["active", "=", true], ["account_id", "!=", false]];
    }

    async setProject(id) {
        this.state.projectId = id;
        this.state.saleOrderId = false;
        this.closeManualMode();
        await this.load();
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "project.project",
                "get_hgr_profitability_report",
                [],
                {
                    project_id: this.state.projectId || false,
                    date_from: this.state.dateFrom || false,
                    date_to: this.state.dateTo || false,
                    sale_order_id: this.state.saleOrderId || false,
                }
            );
        } catch (error) {
            this.notification.add(
                error?.data?.message || _t("The profitability report could not be loaded."),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    formatMoney(value, currencyId = false) {
        return formatCurrency(value || 0, currencyId || this.state.data?.currency_id);
    }

    formatNumber(value) {
        return formatFloat(value || 0, { digits: [false, 2] });
    }

    formatPercent(value) {
        return `${formatFloat(value || 0, { digits: [false, 1] })}%`;
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    setLabourView(view) {
        this.state.labourView = view;
    }

    get timesheetLines() {
        return (this.state.data?.projects || []).flatMap((project) =>
            project.timesheet_details.map((line) => ({
                ...line,
                project_id: project.id,
                project_name: project.name,
                currency_id: project.currency_id,
            }))
        );
    }

    get materialLines() {
        return (this.state.data?.projects || []).flatMap((project) => [
            ...project.vendor_details.map((line) => ({
                ...line,
                key: line.detail_key || `material-${line.id}`,
                project_id: project.id,
                project_name: project.name,
                currency_id: project.currency_id,
            })),
            ...(project.manual_material_details || []).map((line) => ({
                ...line,
                key: `manual-${line.id}`,
                project_id: project.id,
                project_name: project.name,
                currency_id: project.currency_id,
                vendor: line.entered_by,
                invoice: _t("Manual Entry"),
                product: "",
                allocation_percent: 100,
                state: "manual",
            })),
        ]);
    }

    get unmatchedMaterialLines() {
        const options = Object.fromEntries(
            (this.state.data?.projects || []).map((project) => [
                project.id,
                project.quoted_material_options || [],
            ])
        );
        return this.materialLines
            .filter((line) => !line.matched)
            .map((line) => ({
                ...line,
                options: options[line.project_id] || [],
                assignable: line.source === "manual" || Boolean(line.move_line_id),
            }));
    }

    async assignQuotedMaterial(line, event) {
        const saleLineId = Number(event.target.value) || false;
        if (!saleLineId) {
            return;
        }
        try {
            await this.orm.call("project.project", "hgr_assign_quoted_material", [
                [line.project_id],
                saleLineId,
            ], {
                move_line_id: line.source === "manual" ? false : line.move_line_id,
                manual_cost_id: line.source === "manual" ? line.id : false,
            });
            this.notification.add(_t("Material cost matched to the quotation."), { type: "success" });
            await this.load();
        } catch (error) {
            event.target.value = "";
            this.notification.add(error?.data?.message || _t("The material could not be matched."), {
                type: "danger",
            });
        }
    }

    get serviceSummary() {
        return (this.state.data?.projects || []).flatMap((project) =>
            (project.labour_comparison || []).map((row) => ({
                ...row,
                key: `${project.id}-${row.key}`,
                project_name: project.name,
                currency_id: project.currency_id,
            }))
        );
    }

    get costSummaryProjects() {
        return (this.state.data?.projects || []).map((project) => ({
            project,
            labourRows: project.labour_comparison || [],
            materialRows: project.material_comparison || [],
        }));
    }

    get manualEmployeeDomain() {
        return [["active", "=", true]];
    }

    manualPayload() {
        const manual = this.state.manual;
        return {
            entry_type: manual.entryType,
            project_id: this.state.projectId,
            employee_id: manual.employeeId || false,
            sale_line_id: manual.saleLineId || false,
            manual_service_name: manual.manualServiceName.trim(),
            work_category_id: manual.workCategoryId || false,
            product_id: manual.productId || false,
            date: manual.date,
            hours: Number(manual.hours) || 0,
            amount: Number(manual.amount) || 0,
            description: manual.description.trim(),
        };
    }

    resetManualValidation() {
        this.state.manualValidated = false;
        this.state.validationToken = false;
    }

    async openManualMode() {
        if (!this.state.projectId || this.state.data?.projects.length !== 1) {
            this.notification.add(_t("Select one project before using Manual Mode."), {
                type: "warning",
            });
            return;
        }
        this.state.manualOpen = true;
        this.resetManualValidation();
        this.state.manualOptions = await this.orm.call(
            "project.project",
            "get_hgr_profitability_manual_options",
            [this.state.projectId]
        );
    }

    closeManualMode() {
        this.state.manualOpen = false;
        this.resetManualValidation();
    }

    setManualType(type) {
        this.state.manual.entryType = type;
        this.state.manual.employeeId = false;
        this.state.manual.saleLineId = false;
        this.state.manual.isManualService = false;
        this.state.manual.manualServiceName = "";
        this.state.manual.workCategoryId = false;
        this.state.manual.productId = false;
        this.state.manual.hours = "";
        this.state.manual.amount = "";
        this.resetManualValidation();
    }

    setManualEmployee(id) {
        this.state.manual.employeeId = id;
        this.resetManualValidation();
    }

    setManualWorkCategory(id) {
        this.state.manual.workCategoryId = id;
        this.resetManualValidation();
    }

    setManualProduct(id) {
        this.state.manual.productId = id;
        this.resetManualValidation();
    }

    setManualService(event) {
        this.state.manual.isManualService = event.target.value === "manual";
        this.state.manual.saleLineId = this.state.manual.isManualService
            ? false
            : (Number(event.target.value) || false);
        if (!this.state.manual.isManualService) {
            this.state.manual.manualServiceName = "";
        }
        this.resetManualValidation();
    }

    async validateManualEntry() {
        try {
            const result = await this.orm.call(
                "project.project",
                "check_hgr_manual_profitability_entry",
                [this.manualPayload()]
            );
            this.state.validationToken = result.validation_token;
            this.state.manualValidated = true;
            this.notification.add(
                _t("Validation passed. Review the entry, then confirm and save."),
                { type: "success" }
            );
        } catch (error) {
            this.resetManualValidation();
            this.notification.add(error?.data?.message || _t("Validation failed."), {
                type: "danger",
            });
        }
    }

    async saveManualEntry() {
        try {
            await this.orm.call(
                "project.project",
                "create_hgr_manual_profitability_entry",
                [this.manualPayload(), this.state.validationToken]
            );
            this.notification.add(_t("Manual profitability entry saved."), {
                type: "success",
            });
            this.state.manual.description = "";
            this.state.manual.hours = "";
            this.state.manual.amount = "";
            this.closeManualMode();
            await this.load();
        } catch (error) {
            this.resetManualValidation();
            this.notification.add(error?.data?.message || _t("The manual entry could not be saved."), {
                type: "danger",
            });
        }
    }

    async selectProject(projectId) {
        this.state.projectId = projectId;
        this.state.saleOrderId = false;
        await this.load();
    }

    openVendorBills(project = false) {
        const projects = project ? [project] : (this.state.data?.projects || []);
        const ids = [...new Set(projects.flatMap((item) =>
            (item.vendor_details || []).map((line) => line.move_id)
        ).filter(Boolean))];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Vendor Bills"),
            res_model: "account.move",
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", ids]],
            context: { create: false },
        });
    }

    openQuotedOrders(project = false) {
        const projects = project ? [project] : (this.state.data?.projects || []);
        const ids = [...new Set(projects.flatMap((item) => item.sale_order_ids || []))];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Quoted Sales Orders"),
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", ids]],
            context: { create: false },
        });
    }

    openCustomerInvoices(project = false) {
        const projects = project ? [project] : (this.state.data?.projects || []);
        const ids = [...new Set(projects.flatMap((item) => item.invoice_ids || []))];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Customer Invoices"),
            res_model: "account.move",
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", ids]],
            context: { create: false },
        });
    }

    openTimesheets(project = false) {
        const projects = project ? [project] : (this.state.data?.projects || []);
        const ids = projects.flatMap((item) => (item.timesheet_details || []).map((line) => line.id));
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Timesheets"),
            res_model: "account.analytic.line",
            views: [[false, "list"], [false, "form"]],
            domain: [["id", "in", ids]],
            context: {
                create: false,
                list_view_ref: "heiniger_addons.hgr_profitability_timesheet_list",
            },
        });
    }
}

registry.category("actions").add("hgr_project_profitability", HgrProjectProfitability);
