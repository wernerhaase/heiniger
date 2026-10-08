{
    'name': 'Heiniger PDF Editor',
    'version': '19.0.1.1.0',
    'license': 'LGPL-3',
    'depends': ['heiniger_addons', 'base_setup'],
    'external_dependencies': {'python': ['jwt']},
    'data': ['security/ir.model.access.csv', 'security/rules.xml', 'views/settings.xml', 'views/editor.xml'],
    'assets': {'web.assets_backend': [
        'heiniger_pdf_editor/static/src/file_viewer.js',
        'heiniger_pdf_editor/static/src/file_viewer.xml',
    ]},
    'installable': True,
}
