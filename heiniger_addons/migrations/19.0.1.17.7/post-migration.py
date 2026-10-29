def migrate(cr, version):
    """Carry the former single quick tax into the new multi-tax relation."""
    cr.execute("""
        INSERT INTO hgr_bank_statement_line_tax_rel (statement_line_id, tax_id)
        SELECT id, hgr_tax_id
          FROM account_bank_statement_line
         WHERE hgr_tax_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
