"""Split and tag income transactions.

This plugin allows you to split income transactions into pre-tax and post-tax
transactions. The pre-tax transaction will be tagged, allowing you to filter
them out, leaving you only with your net income. The plugin can be configured
as follows:

    plugin "fava_plugins.split_income" "{
        'income': 'Income:Work',
        'net_income': 'Income:Net',
        'taxes': 'Expenses:Taxes',
        'tag': 'pretax',
    }"

These options have the following meaning:

    'income' (default: the Income account): Any entry containing a subaccount
        of this account will be split.
    'net_income' (default: the 'Net' subaccount of the Income account): The
        remainder after substracting taxes from the income account will be
        transferred to the matching subaccount of this account.
    'taxes' (default: the 'Taxes' subaccount  of the Expenses account):
        Any posting whose account matches this regular expression will be
        regarded as pretax expenses.
    'tag' (default: 'pretax'):
        The tag assigned to the transaction containing the pretax income.

So the above settings will turn the following entry

    2018-01-31 * "Employer" "Income"
        Income:Work                  -1000.00 EUR
        Income:Work:Bonus             -100.00 EUR
        Expenses:Taxes                 180.00 EUR
        Expenses:Taxes:Extra            20.00 EUR
        Assets:Account                 900.00 EUR

into

    2018-01-31 * "Employer" "Income"
        Income:Net                    -800.00 EUR
        Income:Net:Bonus              -100.00 EUR
        Assets:Account                 900.00 EUR

    2018-01-31 * "Employer" "Income" #pretax
        Income:Work                  -1000.00 EUR
        Income:Work:Bonus             -100.00 EUR
        Expenses:Taxes                 180.00 EUR
        Expenses:Taxes:Extra            20.00 EUR
        Income:Net                     800.00 EUR
        Income:Net:Bonus               100.00 EUR
"""

from __future__ import annotations

import ast
import collections
import copy
import re
from decimal import Decimal
from typing import Any
from typing import TYPE_CHECKING

from beancount.core import convert
from beancount.core import data
from beancount.core import getters
from beancount.core.inventory import Inventory

if TYPE_CHECKING:
    from beancount.core.data import Directive

__plugins__ = ("split_income",)

SplitIncomeError = collections.namedtuple(
    "SplitIncomeError",
    "source message entry",
)

ZERO = Decimal()


def split_income(
    entries: list[Directive], options_map: Any, config_str: str
) -> tuple[list[Directive], list[SplitIncomeError]]:
    """Split income transactions."""

    errors = []
    new_entries: list[Directive] = []
    new_accounts = set()
    config = {
        "income": options_map["name_income"],
        "net_income": options_map["name_income"] + ":Net",
        "tag": "pretax",
        "taxes": options_map["name_expenses"] + ":Taxes",
    }

    if config_str.strip():
        try:
            expr = ast.literal_eval(config_str)
            config.update(expr)
        except (SyntaxError, ValueError):
            errors.append(
                SplitIncomeError(
                    data.new_metadata(options_map["filename"], 0),
                    f"Syntax error in config: {config_str}",
                    None,
                ),
            )
            return entries, errors

    for entry in entries:
        if not isinstance(entry, data.Transaction) or not any(
            account.startswith(config["income"])
            for account in getters.get_entry_accounts(entry)
        ):
            continue

        # The new entry containing the raw income and taxes.
        new_entry = copy.deepcopy(entry)
        new_entry = new_entry._replace(
            postings=[], tags=frozenset({config["tag"]} | entry.tags)
        )
        new_entries.append(new_entry)

        income: dict[str, Inventory] = collections.defaultdict(Inventory)
        taxes: dict[str, Decimal] = collections.defaultdict(Decimal)
        for posting in list(entry.postings):
            weight = convert.get_weight(posting)  # type: ignore[no-untyped-call]
            if posting.account.startswith(config["income"]):
                new_entry.postings.append(posting)
                entry.postings.remove(posting)
                income[posting.account].add_amount(weight)
            elif re.match(config["taxes"], posting.account):
                new_entry.postings.append(posting)
                entry.postings.remove(posting)
                taxes[weight.currency] += weight.number

        for account, inv in income.items():
            net_account = account.replace(
                config["income"], config["net_income"]
            )
            if net_account not in new_accounts:
                new_accounts.add(net_account)
                new_entries.append(
                    data.Open(
                        data.new_metadata("<split_income>", 0),
                        entry.date,
                        net_account,
                        [],
                        None,
                    )
                )

            for pos in inv:
                amount = pos.units
                number = amount.number + taxes.pop(amount.currency, ZERO)
                data.create_simple_posting(
                    entry, net_account, number, amount.currency
                )
                data.create_simple_posting(
                    new_entry, net_account, -number, amount.currency
                )

    return entries + new_entries, errors
