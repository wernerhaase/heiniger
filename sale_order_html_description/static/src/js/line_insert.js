/** @odoo-module **/

import { SaleOrderLineListRenderer, SaleOrderLineOne2Many, saleOrderLineOne2Many } from '@sale/js/sale_order_line_field/sale_order_line_field';
import { useOpenX2ManyRecord, useX2ManyCrud } from '@web/views/fields/relational_utils';
import { makeContext } from '@web/core/context';
import { registry } from '@web/core/registry';
import { _t } from '@web/core/l10n/translation';

export class HeinigerLineRenderer extends SaleOrderLineListRenderer {
    static recordRowTemplate = 'sale_order_html_description.InsertRecordRow';
    static props = [...SaleOrderLineListRenderer.props, 'insertAfter', 'editHere', 'canInsert'];

    restorePosition(record) {
        const row = this.rootRef.el.querySelector(`[data-id="${record.id}"]`);
        let scroller = row?.parentElement;
        while (scroller && !['auto', 'scroll'].includes(getComputedStyle(scroller).overflowY)) {
            scroller = scroller.parentElement;
        }
        if (!row || !scroller) {
            return () => {};
        }
        const top = row.getBoundingClientRect().top;
        return () => requestAnimationFrame(() => requestAnimationFrame(() => {
            if (!scroller.isConnected) {
                return;
            }
            const current = this.rootRef.el?.querySelector(`[data-id="${record.id}"]`);
            if (current) {
                scroller.scrollTop += current.getBoundingClientRect().top - top;
                current.querySelector('.hgr-line-actions-button')?.focus({ preventScroll: true });
            }
        }));
    }

    insertHere(record, displayType) {
        return this.props.insertAfter(record, displayType, this.restorePosition(record));
    }

    editHere(record) {
        return this.props.editHere(record, this.restorePosition(record));
    }
}

export class HeinigerOrderLines extends SaleOrderLineOne2Many {
    static components = { ...SaleOrderLineOne2Many.components, ListRenderer: HeinigerLineRenderer };

    setup() {
        super.setup();
        const { saveRecord, updateRecord } = useX2ManyCrud(() => this.list, false);
        this.openHere = useOpenX2ManyRecord({
            activeField: this.activeField,
            activeActions: this.activeActions,
            getList: () => this.list,
            isMany2Many: false,
            updateRecord,
            saveRecord: async (record) => {
                // Include all pages before resequencing and leave room for the new line.
                // load() keeps the list's pending edits and unsaved records.
                if (this.insertAnchor) {
                    await this.list.load({ offset: 0, limit: this.list.count + 1 });
                }
                await saveRecord(record);
                if (this.insertAnchor) {
                    await this.list.resequence(record.id, this.insertAnchor.id);
                    // Save & New inserts successive lines in their entered order.
                    this.insertAnchor = record;
                }
            },
        });
    }

    get rendererProps() {
        return {
            ...super.rendererProps,
            canInsert: this.canCreate && !this.props.readonly,
            insertAfter: this.insertAfter.bind(this),
            editHere: this.editHere.bind(this),
        };
    }

    async insertAfter(anchor, displayType, restore) {
        if (!this.canCreate || this.props.readonly || this.openingHere) {
            return;
        }
        this.openingHere = true;
        this.insertAnchor = anchor;
        try {
            await this.openHere({
                context: makeContext([this.props.context, {
                    default_display_type: displayType,
                    hgr_insert_line: true,
                }]),
                title: displayType === 'line_note' ? _t('Insert note below') :
                    displayType === 'line_section' ? _t('Insert section below') : _t('Insert product below'),
                controls: this.controls,
                onClose: () => {
                    this.openingHere = false;
                    this.insertAnchor = null;
                    restore();
                },
            });
        } catch (error) {
            this.openingHere = false;
            this.insertAnchor = null;
            throw error;
        }
    }

    async editHere(record, restore) {
        await this.openHere({
            record,
            context: this.props.context,
            readonly: this.props.readonly,
            controls: this.controls,
            onClose: restore,
        });
    }
}

registry.category('fields').add('hgr_sol_o2m', {
    ...saleOrderLineOne2Many,
    component: HeinigerOrderLines,
    additionalClasses: [...(saleOrderLineOne2Many.additionalClasses || []), 'hgr-order-line-actions'],
});
