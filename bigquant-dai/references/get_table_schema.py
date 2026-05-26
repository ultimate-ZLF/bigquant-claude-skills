"""
获取 BigQuant 数据表的字段及描述。

用法：
    from references.get_table_schema import get_description
    print(get_description('cn_stock_prefactors'))

或命令行：
    python get_table_schema.py cn_stock_prefactors
"""

import requests


def get_description(table_name):
    """
    获取数据表中包含的字段以及描述。

    :param table_name: 表名，如 'cn_stock_prefactors', 'cn_option_basic_info'
    :return: 字段名与描述的文本
    """
    url = (
        "https://bigquant.com/bigapis/data/v1/spacedatasources/"
        "spaces/00000000-0000-0000-0000-000000000000/datasources/"
    )
    url += table_name
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    r = resp.json()["data"]["docs"]

    a = ""
    for k, v in r["schema"].items():
        if isinstance(v, dict):
            a += "{} : {}\n".format(k, v.get("description", ""))
        else:
            a += f"{k}: {v}\n"
    return a


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python get_table_schema.py <table_name>")
        sys.exit(1)
    print(get_description(sys.argv[1]))
