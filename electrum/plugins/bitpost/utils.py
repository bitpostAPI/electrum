def get_fee_units(main_window, default):
    fee_combo_values = ['sats', 'sats/byte']
    if main_window.fx and main_window.fx.is_enabled():
        fee_combo_values.append(main_window.fx.get_currency())
    if default in fee_combo_values:
        fee_combo_values.remove(default)
        fee_combo_values.insert(0, default)
    return fee_combo_values
