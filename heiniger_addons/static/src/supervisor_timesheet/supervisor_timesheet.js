/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class HgrSupervisorTimesheet extends Component {
    static template = "heiniger_addons.SupervisorTimesheet";
    static components = { RecordSelector };
    static props = { ...standardActionServiceProps };

    get hgrBreadcrumbs() {
        return this.env.config?.breadcrumbs || [];
    }

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        const actionContext = this.props.action.context || {};
        this.labels = {
            customer: _t("Customer"),
            project: _t("Project"),
            supervisor: _t("Supervisor"),
            worker: _t("Worker"),
            service: _t("Service"),
            workCategory: _t("Work Category"),
            selectCustomer: _t("Select customer..."),
            selectProject: _t("Select project..."),
            selectCustomerFirst: _t("Select a customer first"),
            selectProjectFirst: _t("Select a project first"),
            selectSupervisor: _t("Select supervisor..."),
            selectWorker: _t("Select worker..."),
            selectService: _t("Select service..."),
            selectWorkCategory: _t("Select work category..."),
            manualService: _t("Other / Manual service"),
            selectWorkerFirst: _t("Select a worker first"),
            noServices: _t("No service items found on the linked sales orders"),
        };
        this.nextLineKey = 1;
        this.nextAttachmentKey = 1;
        this.state = useState({
            partnerId: actionContext.default_partner_id || false,
            projectId: actionContext.default_project_id || false,
            supervisorId: false,
            companyId: actionContext.default_company_id || false,
            date: "",
            description: "",
            serviceLines: [],
            workCategories: [],
            loadingServices: false,
            lines: [this.newLine()],
            attachments: [],
            saving: false,
        });
        onWillStart(async () => {
            const [defaults, workCategories] = await Promise.all([
                this.orm.call(
                    "hgr.supervisor.timesheet",
                    "get_entry_defaults",
                    []
                ),
                this.orm.searchRead(
                    "hgr.work.category",
                    [["active", "=", true]],
                    ["name", "color"],
                    { order: "name" }
                ),
            ]);
            this.state.supervisorId = defaults.supervisor_id;
            this.state.companyId ||= defaults.company_id;
            this.state.date = defaults.date;
            this.state.workCategories = workCategories;
            if (this.state.projectId) {
                await this.loadServiceLines();
            }
        });
    }

    newLine() {
        return {
            key: this.nextLineKey++,
            employeeId: false,
            saleLineId: false,
            isManualService: false,
            manualServiceName: "",
            workCategoryId: false,
            hours: "",
            description: "",
        };
    }

    get projectDomain() {
        const domain = [
            ["allow_timesheets", "=", true],
            ["is_template", "=", false],
            ["active", "=", true],
        ];
        domain.push(["partner_id", "=", this.state.partnerId || 0]);
        return domain;
    }

    get employeeDomain() {
        const domain = [["active", "=", true]];
        if (this.state.companyId) {
            domain.push(["company_id", "=", this.state.companyId]);
        }
        return domain;
    }

    setCustomer(id) {
        this.state.partnerId = id;
        this.state.projectId = false;
        this.state.serviceLines = [];
        for (const line of this.state.lines) {
            line.saleLineId = false;
            line.isManualService = false;
            line.manualServiceName = "";
            line.workCategoryId = false;
        }
    }

    async setProject(id) {
        this.state.projectId = id;
        for (const line of this.state.lines) {
            line.saleLineId = false;
            line.isManualService = false;
            line.manualServiceName = "";
            line.workCategoryId = false;
        }
        await this.loadServiceLines();
    }

    async loadServiceLines() {
        if (!this.state.projectId) {
            this.state.serviceLines = [];
            return;
        }
        this.state.loadingServices = true;
        try {
            this.state.serviceLines = await this.orm.call(
                "hgr.supervisor.timesheet",
                "get_service_sale_lines",
                [this.state.projectId]
            );
        } finally {
            this.state.loadingServices = false;
        }
    }

    setWorker(line, id) {
        line.employeeId = id;
        if (!id) {
            line.saleLineId = false;
            line.isManualService = false;
            line.manualServiceName = "";
        }
    }

    setService(line, event) {
        line.isManualService = event.target.value === "manual";
        line.saleLineId = line.isManualService ? false : (Number(event.target.value) || false);
        if (!line.isManualService) {
            line.manualServiceName = "";
            const service = this.state.serviceLines.find(
                (item) => item.id === line.saleLineId
            );
            if (service?.work_category_id) {
                line.workCategoryId = service.work_category_id;
            }
        }
    }

    serviceSection(line) {
        if (!line.saleLineId) {
            return "";
        }
        const service = this.state.serviceLines.find((item) => item.id === line.saleLineId);
        return service?.section || "";
    }

    setWorkCategory(line, event) {
        line.workCategoryId = Number(event.target.value) || false;
    }

    workCategoryColor(category) {
        if (!category) {
            return 0;
        }
        return category.color || ((category.id - 1) % 11) + 1;
    }

    workCategoryClass(category) {
        const color = this.workCategoryColor(category);
        return color ? `o_hgr_category_color_${color}` : "";
    }

    selectedWorkCategoryClass(categoryId) {
        const category = this.state.workCategories.find((item) => item.id === categoryId);
        return this.workCategoryClass(category);
    }

    addLine() {
        this.state.lines.push(this.newLine());
    }

    removeLine(key) {
        if (this.state.lines.length === 1) {
            Object.assign(this.state.lines[0], this.newLine());
            return;
        }
        const index = this.state.lines.findIndex((line) => line.key === key);
        if (index >= 0) {
            this.state.lines.splice(index, 1);
        }
    }

    attachmentMimetype(file) {
        if (file.type) {
            return file.type.toLowerCase();
        }
        const extension = file.name.split(".").pop()?.toLowerCase();
        return {
            pdf: "application/pdf",
            heic: "image/heic",
            heif: "image/heif",
            jpeg: "image/jpeg",
            jpg: "image/jpeg",
            png: "image/png",
            tif: "image/tiff",
            tiff: "image/tiff",
            webp: "image/webp",
        }[extension] || "";
    }

    readFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const result = String(reader.result || "");
                resolve(result.includes(",") ? result.split(",", 2)[1] : "");
            };
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(file);
        });
    }

    async onFilesSelected(event) {
        const files = Array.from(event.target.files || []);
        event.target.value = "";
        for (const file of files) {
            if (this.state.attachments.length >= 10) {
                this.notification.add(_t("You can attach at most 10 work reports."), {
                    type: "warning",
                });
                break;
            }
            const mimetype = this.attachmentMimetype(file);
            if (!(mimetype === "application/pdf" || mimetype.startsWith("image/"))) {
                this.notification.add(
                    _t("%s is not a supported image or PDF file.", file.name),
                    { type: "warning" }
                );
                continue;
            }
            if (!file.size || file.size > 10 * 1024 * 1024) {
                this.notification.add(
                    _t("%s is empty or exceeds the 10 MB file limit.", file.name),
                    { type: "warning" }
                );
                continue;
            }
            const totalSize = this.state.attachments.reduce(
                (total, attachment) => total + attachment.size,
                file.size
            );
            if (totalSize > 25 * 1024 * 1024) {
                this.notification.add(
                    _t("Work report attachments cannot exceed 25 MB in total."),
                    { type: "warning" }
                );
                break;
            }
            try {
                this.state.attachments.push({
                    key: this.nextAttachmentKey++,
                    name: file.name,
                    mimetype,
                    size: file.size,
                    datas: await this.readFile(file),
                });
            } catch {
                this.notification.add(
                    _t("%s could not be read. Please attach it again.", file.name),
                    { type: "danger" }
                );
            }
        }
    }

    removeAttachment(key) {
        const index = this.state.attachments.findIndex(
            (attachment) => attachment.key === key
        );
        if (index >= 0) {
            this.state.attachments.splice(index, 1);
        }
    }

    attachmentSize(size) {
        if (size < 1024 * 1024) {
            return `${Math.max(1, Math.round(size / 1024))} KB`;
        }
        return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    }

    validate() {
        if (!this.state.partnerId || !this.state.projectId || !this.state.supervisorId || !this.state.date) {
            return _t("Complete the customer, project, supervisor, and date.");
        }
        const invalidLine = this.state.lines.some(
            (line) => !line.employeeId
                || (!line.saleLineId && !line.manualServiceName.trim())
                || !line.workCategoryId
                || Number(line.hours) <= 0
        );
        if (invalidLine) {
            return _t("Every line needs a worker, service, work category, and positive hours.");
        }
        return false;
    }

    async save() {
        const error = this.validate();
        if (error) {
            this.notification.add(error, { type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            const result = await this.orm.call("hgr.supervisor.timesheet", "create_from_ui", [{
                partner_id: this.state.partnerId,
                project_id: this.state.projectId,
                supervisor_id: this.state.supervisorId,
                date: this.state.date,
                description: this.state.description,
                attachments: this.state.attachments.map((attachment) => ({
                    name: attachment.name,
                    mimetype: attachment.mimetype,
                    datas: attachment.datas,
                })),
                lines: this.state.lines.map((line) => ({
                    employee_id: line.employeeId,
                    sale_line_id: line.saleLineId,
                    manual_service_name: line.manualServiceName.trim(),
                    work_category_id: line.workCategoryId,
                    unit_amount: Number(line.hours),
                    name: line.description.trim(),
                })),
            }]);
            this.notification.add(
                _t("%s timesheet entries saved.", result.count),
                { type: "success" }
            );
            this.state.description = "";
            this.state.lines.splice(0, this.state.lines.length, this.newLine());
            this.state.attachments.splice(0, this.state.attachments.length);
        } catch (error) {
            this.notification.add(
                error?.data?.message || _t("The timesheet entries could not be saved."),
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("hgr_supervisor_timesheet", HgrSupervisorTimesheet);
