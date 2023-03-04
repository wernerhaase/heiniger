{
    'name': 'Full Screen Form View On Enterprise',
    'version': '1.0',
    'summary': 'Hide the chatter panel to make the form view is wider',
    'description': 'Hide the chatter panel to make the form view is wider',
    'author': "Sonny Huynh",
    'category': 'Extra Tools',
    'depends': ['base'],

    'data': [],
    'assets': {
        'web.assets_backend': [
            'full_screen_form_view/static/src/js/*.js',
            'full_screen_form_view/static/src/scss/layout.scss',
        ],
    },


    'qweb': [],
    # only loaded in demonstration mode
    'demo': [],
    'images': [
        'static/description/banner.gif',
    ],
    'license': 'OPL-1',
    'price': 29.00,
    'currency': 'EUR',
}