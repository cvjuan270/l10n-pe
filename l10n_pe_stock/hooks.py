def post_init_hook(cr, registry):
    # update stock_picking.kardex_account_dote with the date_done of the stock_picking
    cr.execute(
        """
        update stock_picking
        set kardex_account_date = (date_done AT TIME ZONE 'UTC' AT TIME ZONE 'America/Lima')::DATE
        where company_id in(
        select rc.id from res_company rc where partner_id in (
        select rp.id from res_partner rp where rp.country_id in (
        select rc.id from res_country rc where rc.code = 'PE')))
        and state ='done'
        and id in (
        select picking_id from stock_move where id in (
        select stock_move_id from account_move where stock_move_id is not null
        ))
    """
    )
    # update account_move.kardex_account_date with the date of the account_move
    cr.execute(
        """
        update account_move
        set kardex_account_date  = "date"
        where stock_move_id is not null
    """
    )
