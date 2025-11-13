def replace_quotes_in_dict(d):
    for key, value in d.items():
        if isinstance(value, dict):
            replace_quotes_in_dict(value)
        elif isinstance(value, str):
            d[key] = value.replace("'", "''")
