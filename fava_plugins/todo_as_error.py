"""Create errors for entries 'todo' metadata.

When enabling the `todo_as_error`-plugin, transactions with the
`todo`-metadata-key will be added as Beancount errors, displaying the value of
the `todo`-metadata-entry as the error description.

    plugin "fava_plugins.todo_as_error"

    2017-12-27 * "" "Groceries"
      todo: "Put the milk into the fridge"
      Expenses:Groceries   150.00 USD
      Assets:Cash
"""

from __future__ import annotations

import collections
from typing import Any
from typing import TYPE_CHECKING

from beancount.core.data import Transaction

if TYPE_CHECKING:
    from beancount.core.data import Directive

__plugins__ = [
    "todo_as_error",
]

TodoError = collections.namedtuple("TodoError", "source message entry")


def todo_as_error(
    entries: list[Directive],
    _: Any,
) -> tuple[list[Directive], list[TodoError]]:
    """Create errors for entries 'todo' metadata."""
    errors = []

    for entry in entries:
        if isinstance(entry, Transaction) and "todo" in entry.meta:
            errors.append(TodoError(entry.meta, entry.meta["todo"], entry))

    return entries, errors
