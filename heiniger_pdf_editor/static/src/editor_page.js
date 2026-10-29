/* Standalone ONLYOFFICE host page; no Odoo backend bundle needed. */
(() => {
    const status = document.getElementById('save-status');
    const error = document.getElementById('editor-error');
    const showError = (message) => {
        error.hidden = false;
        error.textContent = message;
    };
    if (!window.DocsAPI) {
        showError('The PDF editor service could not be reached. Your attachment is unchanged. Ask your administrator to check the ONLYOFFICE connection.');
        return;
    }
    const config = JSON.parse(document.getElementById('editor-config').dataset.config);
    let changedAt = 0;
    let acknowledged = 0;
    config.events = {
        onDocumentStateChange(event) {
            if (event.data) {
                changedAt = Date.now();
                status.textContent = 'Changes in editor. Use Save and wait for “Saved to Odoo”.';
            }
        },
        onError(event) {
            showError(event.data?.errorDescription || 'The editor encountered an error. Download your edited copy before closing.');
        },
    };
    new window.DocsAPI.DocEditor('pdf-editor', config);
    const poll = window.setInterval(async () => {
        try {
            const requestedAt = Date.now();
            const response = await fetch('/heiniger/pdf/status/' + document.body.dataset.session, {cache: 'no-store'});
            if (!response.ok) return;
            const data = await response.json();
            // Use server-relative age to avoid depending on the user's clock.
            const saved = data.saved_at ? requestedAt - data.save_age_ms : 0;
            if (saved && saved >= changedAt && saved > acknowledged) {
                acknowledged = saved;
                status.textContent = 'Saved to Odoo. The previous PDF is kept as a backup.';
            }
        } catch { /* A transient status failure must not claim that saving succeeded. */ }
    }, 3000);
    window.addEventListener('beforeunload', (event) => {
        if (changedAt > acknowledged) {
            event.preventDefault();
            event.returnValue = '';
        }
    });
    window.addEventListener('pagehide', () => window.clearInterval(poll));
})();
